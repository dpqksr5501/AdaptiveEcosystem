"""Verify saved island fauna and render the existing freshwater reach in PIE."""

from collections import Counter
from hashlib import sha256
import json
from itertools import combinations, product
import math
from pathlib import Path
import re
import sys
import time
import traceback

import unreal as u


editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
out = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit"
authored = json.loads((out / "IslandFaunaAuthoring.json").read_text(encoding="utf-8"))
inspect = u.EcoCreatureInspectionLibrary
result = {"errors": [], "samples": [], "capture_files": []}
command = u.SystemLibrary.get_command_line()
audit_label = re.search(r"(?:^|\s)-EcoIslandAuditLabel=([A-Za-z0-9_]{1,32})(?:\s|$)", command)
population_duration = re.search(r"(?:^|\s)-EcoIslandPopulationSeconds=(\d+)(?:\s|$)", command)
population_duration = int(population_duration[1]) if population_duration else None
population_without_forage_soil = "-EcoIslandPopulationWithoutForageSoil" in command.split()
survey_second_mink_shore = "-EcoIslandSurveySecondMinkShore" in command.split()
survey_local_mink_water = "-EcoIslandSurveyLocalMinkWater" in command.split()
second_mink_trial_match = re.search(r"(?:^|\s)-EcoIslandSecondMinkTrial=(\d+)(?:\s|$)", command)
second_mink_trial = int(second_mink_trial_match[1]) if second_mink_trial_match else None
second_mink_near_start = "-EcoIslandSecondMinkNearStart" in command.split()
second_mink_deep_budget = "-EcoIslandSecondMinkDeepBudget" in command.split()
second_mink_flood = "-EcoIslandSecondMinkFlood" in command.split()
second_mink_flood_cover_bank = "-EcoIslandSecondMinkFloodCoverBank" in command.split()
second_mink_flood_survey = "-EcoIslandSecondMinkFloodSurvey" in command.split()
second_mink_flood_connector = "-EcoIslandSecondMinkFloodConnector" in command.split()
second_mink_flood_platform = "-EcoIslandSecondMinkFloodPlatform" in command.split()
second_mink_exit_cover = "-EcoIslandSecondMinkExitCover" in command.split()
second_mink_remove_exit_cover = "-EcoIslandSecondMinkRemoveExitCover" in command.split()
second_mink_flood_ramp = "-EcoIslandSecondMinkFloodRamp" in command.split()
second_mink_wide_ramp = "-EcoIslandSecondMinkWideRamp" in command.split()
second_mink_dry_bank = "-EcoIslandSecondMinkDryBank" in command.split()
second_mink_bank_layout = "-EcoIslandSecondMinkBankLayout" in command.split()
save_mink_bank_layout = "-EcoIslandSaveMinkBankLayout" in command.split()
verify_mink_bank_layout = "-EcoIslandVerifyMinkBankLayout" in command.split()
second_mink_saved_flood = verify_mink_bank_layout and "-EcoIslandSecondMinkSavedFlood" in command.split()
focused_mink_ramp = "-EcoIslandFocusMinkRamp" in command.split()
survey_nursery_depth = "-EcoIslandSurveyNurseryDepth" in command.split()
survey_water_forage = "-EcoIslandSurveyWaterForage" in command.split()
survey_water_detour = "-EcoIslandVerifyWaterDetour" in command.split()
capture_water_forage_grid = "-EcoIslandCaptureWaterForageGrid" in command.split()
save_water_forage = "-EcoIslandSaveDriftForage" in command.split()
save_deep_shelf = "-EcoIslandSaveDeepShelf" in command.split()
save_island_deer_presentation = "-EcoIslandSaveDeerPresentation" in command.split()
save_island_weather = "-EcoIslandSaveWeatherPresentation" in command.split()
save_mink_bank_surface = "-EcoIslandSaveMinkBankSurface" in command.split()
save_river_rat_refuge = "-EcoIslandSaveRiverRatRefuge" in command.split()
deep_shelf_offset_cm = -32.
water_forage_split = "-EcoIslandTrialWaterForageSplit" in command.split()
water_forage_drift = water_forage_split and "-EcoIslandWaterForageAtDrift" in command.split()
water_forage_small_fish = water_forage_split and "-EcoIslandWaterForageSmallFish" in command.split()
water_forage_from_drift = water_forage_small_fish and "-EcoIslandWaterForageFromDrift" in command.split()
water_forage_shared = "-EcoIslandWaterForageShared" in command.split()
drift_seasonal_trial = "-EcoIslandDriftSeasonalTrial" in command.split()
drift_visual_trial = "-EcoIslandDriftVisualTrial" in command.split()
drift_surface_trial = "-EcoIslandDriftSurfaceTrial" in command.split()
drift_shore_trial = "-EcoIslandDriftShoreTrial" in command.split()
DRIFT_SHORE_HABITAT = "IslandDriftSeasonalShore"
water_forage_drawdown = "-EcoIslandWaterForageSharedDrawdown" in command.split()
water_forage_split_percent = re.search(r"(?:^|\s)-EcoIslandWaterForageSplitPercent=(\d+)(?:\s|$)", command)
water_forage_split_fraction = int(water_forage_split_percent[1]) / 100. if water_forage_split_percent else .35
if not 0. < water_forage_split_fraction < 1.:
    raise RuntimeError("Water forage split percentage must be in 1–99")
water_forage_duration = re.search(r"(?:^|\s)-EcoIslandWaterForageSeconds=(420|720)(?:\s|$)", command)
water_forage_duration = int(water_forage_duration[1]) if water_forage_duration else (
    420 if "-EcoIslandWaterForageExtended" in command.split() else 0)
nursery_drawdown = "-EcoIslandNurseryDrawdown" in command.split()
nursery_fry_match = re.search(r"(?:^|\s)-EcoIslandNurseryFry=(Control|Drawdown)(?:\s|$)", command)
nursery_fry = nursery_fry_match[1] if nursery_fry_match else None
trial_second_eagle_perch = "-EcoIslandTrialSecondEaglePerch" in command.split()
survey_forage_water = "-EcoIslandSurveyForageWater" in command.split()
local_soil_trial_match = re.search(r"(?:^|\s)-EcoIslandLocalForageSoil=(Rain|Water)(?:\s|$)", command)
local_soil_trial = local_soil_trial_match[1] if local_soil_trial_match else None
land_forage_match = re.search(r"(?:^|\s)-EcoIslandLowerRiverLandForage=(Low|High|BankAccess|SavedAccess|RootOnlyHigh)(?:\s|$)", command)
land_forage_trial = land_forage_match[1] if land_forage_match else None
feeding_track_match = re.search(r"(?:^|\s)-EcoIslandFeedingTrack=([1-9]\d*(?:,[1-9]\d*)*)(?:\s|$)", command)
feeding_track_ids = sorted({int(agent) for agent in feeding_track_match[1].split(",")}) if feeding_track_match else []
player_trial_match = re.search(r"(?:^|\s)-EcoIslandPlayerPassage=(Still|Sneak|Run)(?:\s|$)", command)
player_trial = player_trial_match[1] if player_trial_match else None
combat_trial_match = re.search(r"(?:^|\s)-EcoIslandCombatCarrion=(Present|Attack|Rifle|RiflePresent)(?:\s|$)", command)
combat_trial = combat_trial_match[1] if combat_trial_match else None
rifle_combat_trial = combat_trial in {"Rifle", "RiflePresent"}
combat_start_match = re.search(r"(?:^|\s)-EcoIslandCombatStart=(\d+)(?:\s|$)", command)
combat_start = int(combat_start_match[1]) if combat_start_match else 16
combat_victim_match = re.search(r"(?:^|\s)-EcoIslandCombatVictim=(\d+)(?:\s|$)", command)
combat_victim = int(combat_victim_match[1]) if combat_victim_match else 49
forage_intent_match = re.search(r"(?:^|\s)-EcoIslandForageIntent=(Control|Alternate|Expired|Switch|Hold)(?:\s|$)", command)
forage_intent = forage_intent_match[1] if forage_intent_match else None
forage_guild_trial = "-EcoIslandOpenMeadowBrowse" in command.split()
forage_guild_west = "-EcoIslandWestMeadowBrowse" in command.split()
forage_half_meal = "-EcoIslandWestMeadowHalfMeal" in command.split()
stage_bounds_trial = re.search(r"(?:^|\s)-EcoIslandTrialStageBounds=(Grassland|Riverbank|Highland)(?:\s|$)", command)
water_species = {"AriakeCatfish", "CommonCarp", "UnidentifiedFish", "Mink"}
highland_rat_sites = ((48960., 49690., 3137.184), (50200., 49470., 3137.184))
highland_near_cover_sites = ((52812.127, 48524.082, 3137.057), (52768.811, 48304.862, 3136.880))
if "-EcoIslandAccessAudit" in command.split():
    layout = ("inlet" if "-EcoIslandMoveSlowShelfToInlet" in command.split()
              else "roots" if "-EcoIslandMoveSlowShelfToRoots" in command.split()
              else "shelf" if "-EcoIslandMoveSlowShelf" in command.split()
              else "saved" if "-EcoIslandVerifySavedShelf" in command.split() else "baseline")
    meal_match = re.search(r"(?:^|\s)-EcoAdaptiveRoutineMask=(\d+)(?:\s|$)", command)
    meal_suffix = f"_routine{meal_match.group(1)}" if meal_match else ""
    record_feeding = bool(feeding_track_ids or player_trial or forage_intent or trial_second_eagle_perch
                          or second_mink_trial is not None
                          or nursery_drawdown or nursery_fry) or "-EcoIslandFeedingHistory" in command.split()
    habitat_suffix = "_habitat" if "-EcoHabitatDynamics" in command.split() else ""
    seed_match = re.search(r"(?:^|\s)-EcoV3Seed=(\d+)(?:\s|$)", command)
    seed = seed_match.group(1) if seed_match else "default"
    shore_profile = "-EcoIslandMinkShoreProfile" in command.split() or "-EcoIslandMinkShoreTrial" in command.split()
    connector_trial = "-EcoIslandMinkConnectorTrial" in command.split()
    near_food_trial = connector_trial and "-EcoIslandMinkNearFood" in command.split()
    split_food_trial = near_food_trial and "-EcoIslandMinkSplitFood" in command.split()
    validate_shore_on_start = split_food_trial and "-EcoIslandValidateShoreOnStart" in command.split()
    shore_rain_trial = "-EcoIslandShoreRainTrial" in command.split()
    cover_shore_bank = shore_rain_trial and "-EcoIslandRainCoverBank" in command.split()
    survey_flood_exit = shore_rain_trial and "-EcoIslandSurveyFloodExit" in command.split()
    high_bank_match = re.search(r"(?:^|\s)-EcoIslandHighBankTrial=(\d+)(?:\s|$)", command)
    high_bank_trial = int(high_bank_match.group(1)) if shore_rain_trial and high_bank_match else None
    verify_high_bank = "-EcoIslandVerifyHighBank" in command.split()
    audit_nursery = "-EcoIslandAuditNursery" in command.split()
    eagle_prey_trial = "-EcoIslandEaglePreyTrial" in command.split()
    eagle_fixed_ids = "-EcoIslandEagleFixedIds" in command.split()
    survey_highland = "-EcoIslandSurveyHighland" in command.split()
    cover_trial = re.search(r"(?:^|\s)-EcoIslandHighlandCover=(Control|Boulders|Sight)(?:\s|$)", command)
    cover_trial = cover_trial.group(1) if cover_trial else None
    near_cover = "-EcoIslandNearCover" in command.split()
    rat_refuge_mode = re.search(r"(?:^|\s)-EcoIslandRatRefuge=(Control|Target|Narrow)(?:\s|$)", command)
    rat_refuge_mode = rat_refuge_mode.group(1) if rat_refuge_mode else None
    river_rat_refuge = re.search(r"(?:^|\s)-EcoIslandRiverRatRefuge=(Control|Narrow|NearControl|NearNarrow|NearCovered|AlignedCovered|ApproachCovered|Saved)(?:\s|$)", command)
    river_rat_refuge = river_rat_refuge.group(1) if river_rat_refuge else None
    river_rat_shift_mouth = "-EcoIslandShiftRatCheckpointMouth" in command.split()
    if river_rat_shift_mouth and (river_rat_refuge != "ApproachCovered" or "-EcoIslandCheckpoint=Load" not in command.split()):
        raise RuntimeError("Shifted rat mouth is only supported in an ApproachCovered checkpoint load")
    if river_rat_refuge and (not audit_label or population_duration or rat_refuge_mode or eagle_fixed_ids):
        raise RuntimeError("Riverbank rat refuge requires a labeled full run with the saved founder layout")
    if rat_refuge_mode and not (audit_label and eagle_fixed_ids and near_cover and cover_trial == "Sight"):
        raise RuntimeError("Rat refuge trial needs a unique label, fixed eagle IDs, and the near-cover sight setup")
    survey_seams = "-EcoIslandSurveySeams" in command.split()
    grassland_passage_saved = "-EcoIslandVerifySavedGrasslandPassage" in command.split()
    grassland_existing_route_trial = "-EcoIslandGrasslandExistingRoute" in command.split()
    grassland_forage_network = "-EcoIslandGrasslandForageNetwork" in command.split()
    grassland_forage_stop = grassland_forage_network and "-EcoIslandGrasslandForageStop" in command.split()
    grassland_forage_near_entry = grassland_forage_stop and "-EcoIslandGrasslandForageNearEntry" in command.split()
    save_grassland_passage = "-EcoIslandSaveGrasslandPassage" in command.split()
    hold_grassland_passage = "-EcoIslandHoldGrasslandPassage" in command.split()
    grassland_passage_trial = "-EcoIslandGrasslandPassageTrial" in command.split()
    grassland_near_forage = grassland_passage_trial and "-EcoIslandGrasslandNearForage" in command.split()
    grassland_sparse_approach = grassland_near_forage and "-EcoIslandGrasslandSparseApproach" in command.split()
    corridor_approach = "-EcoIslandTransitionApproach" in command.split()
    corridor_trial = "-EcoIslandTransitionRegion" in command.split()
    corridor_founder = corridor_trial and "-EcoIslandTransitionFounder" in command.split()
    corridor_control = corridor_trial and "-EcoIslandTransitionControl" in command.split()
    corridor_habitat = corridor_control and "-EcoIslandTransitionHabitat" in command.split()
    habitat_founder = corridor_habitat and "-EcoIslandHabitatFounder" in command.split()
    habitat_near = habitat_founder and "-EcoIslandHabitatNearSeam" in command.split()
    habitat_wet = habitat_founder and "-EcoIslandHabitatMoist" in command.split()
    habitat_region_weather = corridor_habitat and "-EcoIslandHabitatRiverWeather" in command.split()
    habitat_approach = habitat_region_weather and "-EcoIslandHabitatRiverApproach" in command.split()
    habitat_saved = "-EcoIslandVerifySavedHabitat" in command.split()
    highland_approach_trial = "-EcoIslandHighlandApproachTrial" in command.split()
    save_highland_approach = "-EcoIslandSaveHighlandApproach" in command.split()
    habitat_author = "-EcoIslandSaveHabitat" in command.split()
    corridor_checkpoint = re.search(r"(?:^|\s)-EcoIslandTransitionCheckpoint=(Save|Load)(?:\s|$)", command)
    corridor_checkpoint = corridor_checkpoint.group(1) if corridor_founder and corridor_checkpoint else None
    corridor_blocked = corridor_checkpoint == "Load" and "-EcoIslandTransitionBlockExit" in command.split()
    corridor_wall = corridor_checkpoint == "Load" and "-EcoIslandTransitionWall" in command.split()
    audit_vegetation = "-EcoIslandAuditVegetation" in command.split()
    meadow_layout = re.search(r"(?:^|\s)-EcoIslandMeadow=(Control|Spread|Split|Shared)(?:\s|$)", command)
    meadow_layout = meadow_layout.group(1) if meadow_layout else None
    rain_pattern = re.search(r"(?:^|\s)-EcoIslandRainPattern=(Block|Pulses)(?:\s|$)", command)
    rain_pattern = rain_pattern.group(1) if rain_pattern else None
    regional_rain = bool(rain_pattern and "-EcoIslandRegionalRain" in command.split())
    trial_forage_soil = "-EcoIslandTrialForageSoil" in command.split()
    if trial_forage_soil and not (regional_rain and audit_vegetation and audit_label):
        raise RuntimeError("Forage soil comparison needs a labeled regional rain and vegetation audit")
    checkpoint = re.search(r"(?:^|\s)-EcoIslandCheckpoint=(Save|Load)(?:\s|$)", command)
    checkpoint = checkpoint.group(1) if checkpoint else None
    if water_forage_drawdown and (not water_forage_shared or checkpoint != "Load"):
        raise RuntimeError("Shared water forage drawdown requires its matching checkpoint load")
    checkpoint_drift = checkpoint is not None and "-EcoIslandCheckpointDriftForage" in command.split()
    checkpoint_forage_soil = checkpoint is not None and "-EcoIslandCheckpointForageSoil" in command.split()
    verify_saved_shore = shore_rain_trial or "-EcoIslandVerifySavedMinkShore" in command.split()
    eagle_perch_trial = "-EcoIslandEaglePerchTrial" in command.split()
    verify_eagle_perch = "-EcoIslandVerifyEaglePerch" in command.split()
    if trial_second_eagle_perch and (not verify_eagle_perch or eagle_perch_trial):
        raise RuntimeError("Second eagle perch trial needs the saved perch layout")
    shore_suffix = "_connector" if connector_trial else "_shore" if shore_profile else ""
    if near_food_trial:
        shore_suffix += "_near"
    if split_food_trial:
        shore_suffix += "_split"
    if validate_shore_on_start:
        shore_suffix += "_startup"
    if verify_saved_shore:
        shore_suffix += "_saved_mink"
    if eagle_perch_trial:
        shore_suffix += "_perches"
    if verify_eagle_perch:
        shore_suffix += "_saved_perch"
    if shore_rain_trial:
        shore_suffix += "_rain"
    if cover_shore_bank:
        shore_suffix += "_bank"
    if survey_flood_exit:
        shore_suffix += "_survey"
    if high_bank_trial is not None:
        shore_suffix += f"_high{high_bank_trial}"
    if verify_high_bank:
        shore_suffix += "_saved_high"
    if audit_nursery:
        shore_suffix += "_nursery"
    if eagle_prey_trial:
        shore_suffix += "_eagle_prey"
    if eagle_fixed_ids:
        shore_suffix += "_eagle_fixed_ids"
    if survey_highland:
        shore_suffix += "_highland_ground"
    if cover_trial:
        shore_suffix += f"_cover_{cover_trial.lower()}"
    if near_cover:
        shore_suffix += "_near"
    if survey_seams:
        shore_suffix += "_seams"
    if corridor_trial:
        shore_suffix += "_transition_region"
    if corridor_approach:
        shore_suffix += "_approach"
    if corridor_founder:
        shore_suffix += "_founder"
    if corridor_control:
        shore_suffix += "_control"
    if corridor_habitat:
        shore_suffix += "_habitat"
    if habitat_founder:
        shore_suffix += "_rabbit"
    if habitat_near:
        shore_suffix += "_near"
    if habitat_wet:
        shore_suffix += "_moist"
    if habitat_region_weather:
        shore_suffix += "_river_weather"
    if habitat_approach:
        shore_suffix += "_river_approach"
    if habitat_saved:
        shore_suffix += "_persisted"
    if corridor_checkpoint:
        shore_suffix += f"_transit_{corridor_checkpoint.lower()}"
    if corridor_blocked:
        shore_suffix += "_blocked"
    if corridor_wall:
        shore_suffix += "_wall"
    if audit_vegetation:
        shore_suffix += "_vegetation"
    if meadow_layout:
        shore_suffix += f"_meadow_{meadow_layout.lower()}"
    if rain_pattern:
        shore_suffix += f"_rain_{rain_pattern.lower()}"
    if regional_rain:
        shore_suffix += "_regional"
    if checkpoint:
        shore_suffix += f"_checkpoint_{checkpoint.lower()}"
    out = out / f"IslandAccess_{seed}_{layout}{meal_suffix}{'_feeding' if record_feeding else ''}{shore_suffix}{habitat_suffix}"
    if habitat_saved and checkpoint:
        out = out.parent / f"IslandSavedHabitat_{seed}_{checkpoint.lower()}"
    if feeding_track_ids:
        track_key = f"{out.name}:{feeding_track_ids}".encode("utf-8")
        out = out.with_name(f"IslandFeedingTrack_{seed}_{sha256(track_key).hexdigest()[:12]}")
        result["feeding_track"] = {"agent_ids": feeding_track_ids, "interval_seconds": .25, "samples": []}
    if player_trial:
        trial_key = sha256(out.name.encode("utf-8")).hexdigest()[:12]
        out = out.with_name(f"IslandPlayer_{seed}_{player_trial}_{trial_key}")
        result["player_passage"] = {"mode": player_trial, "samples": []}
    if forage_intent:
        intent_key = sha256(out.name.encode("utf-8")).hexdigest()[:12]
        out = out.with_name(f"IslandForageIntent_{seed}_{forage_intent}_{intent_key}")
        requested_patch = "IslandForageWestMeadow" if forage_intent in ("Switch", "Hold") else "IslandForageOpenMeadow"
        result["forage_intent"] = {"mode": forage_intent, "agent_id": 44, "requested_patch": requested_patch,
                                  "submissions": [], "samples": []}
    if survey_second_mink_shore:
        shore_key = sha256(out.name.encode("utf-8")).hexdigest()[:12]
        out = out.with_name(f"IslandSecondMinkShore_{seed}_{shore_key}")
    if survey_nursery_depth:
        if not (shore_rain_trial and verify_high_bank):
            raise RuntimeError("Nursery depth survey needs the saved high-bank rain run")
        depth_key = sha256(out.name.encode("utf-8")).hexdigest()[:12]
        out = out.with_name(f"IslandNurseryDepth_{seed}_{depth_key}")
        result["nursery_depth_survey"] = {}
    if nursery_drawdown:
        if not (shore_rain_trial and verify_high_bank and audit_nursery and audit_label):
            raise RuntimeError("Nursery drawdown needs the saved nursery rain run and an audit label")
        result["nursery_drawdown"] = {"events": {}}
    if nursery_fry:
        if nursery_drawdown or not (shore_rain_trial and verify_high_bank and audit_nursery and audit_label):
            raise RuntimeError("Nursery fry comparison needs the saved nursery rain run and a distinct audit label")
        result["nursery_fry"] = {"mode": nursery_fry, "events": {}, "samples": [], "payments": []}
    if trial_second_eagle_perch:
        perch_key = sha256(out.name.encode("utf-8")).hexdigest()[:12]
        out = out.with_name(f"IslandSecondEagle_{seed}_{perch_key}")
    if audit_label:
        out = out.with_name(f"Island_{seed}_{audit_label[1]}")
    out.mkdir(parents=True, exist_ok=True)
    result["layout"] = layout
    result["water_target_changes"] = []
    result["record_gameplay_reasons"] = record_feeding
    result["shore_profile_requested"] = shore_profile or connector_trial
    result["connector_trial"] = connector_trial
    result["near_food_trial"] = near_food_trial
    result["split_food_trial"] = split_food_trial
    result["validate_shore_on_start"] = validate_shore_on_start
    result["verify_saved_shore"] = verify_saved_shore
    result["eagle_perch_trial"] = eagle_perch_trial
    result["verify_eagle_perch"] = verify_eagle_perch
    result["shore_rain_trial"] = shore_rain_trial
    result["cover_shore_bank"] = cover_shore_bank
    result["survey_flood_exit"] = survey_flood_exit
    result["high_bank_trial"] = high_bank_trial
    result["verify_high_bank"] = verify_high_bank
    result["audit_nursery"] = audit_nursery
    result["eagle_prey_trial"] = eagle_prey_trial
    result["eagle_fixed_ids"] = eagle_fixed_ids
    result["survey_highland"] = survey_highland
    result["cover_trial"] = cover_trial
    result["near_cover"] = near_cover
    result["survey_seams"] = survey_seams
    result["grassland_passage_trial"] = grassland_passage_trial
    result["grassland_passage_saved"] = grassland_passage_saved or grassland_forage_network or grassland_existing_route_trial
    result["grassland_forage_network"] = grassland_forage_network
    result["grassland_forage_stop"] = grassland_forage_stop
    result["grassland_forage_near_entry"] = grassland_forage_near_entry
    result["save_grassland_passage"] = save_grassland_passage
    result["hold_grassland_passage"] = hold_grassland_passage
    result["grassland_near_forage"] = grassland_near_forage or save_grassland_passage
    result["grassland_sparse_approach"] = grassland_sparse_approach or save_grassland_passage
    result["transition_region_trial"] = corridor_trial
    result["transition_extended_approach"] = corridor_approach
    result["highland_approach_trial"] = highland_approach_trial
    result["save_highland_approach"] = save_highland_approach
    result["transition_founder_trial"] = corridor_founder
    result["transition_control"] = corridor_control
    result["transition_habitat"] = corridor_habitat
    result["transition_habitat_founder"] = habitat_founder
    result["transition_habitat_near"] = habitat_near
    result["transition_habitat_moist"] = habitat_wet
    result["transition_habitat_river_weather"] = habitat_region_weather
    result["transition_habitat_river_approach"] = habitat_approach
    result["transition_habitat_saved"] = habitat_saved
    result["transition_habitat_author"] = habitat_author
    result["transition_checkpoint"] = corridor_checkpoint
    result["transition_blocked_exit"] = corridor_blocked
    result["transition_wall"] = corridor_wall
    result["transition_checkpoint_slot"] = f"IslandTransit_{seed}" if corridor_checkpoint else None
    result["audit_vegetation"] = audit_vegetation
    result["meadow_layout"] = meadow_layout
    result["rain_pattern"] = rain_pattern
    result["regional_rain"] = regional_rain
    result["trial_forage_soil"] = trial_forage_soil
    result["local_soil_trial"] = local_soil_trial
    result["checkpoint_mode"] = checkpoint
    result["checkpoint_drift"] = checkpoint_drift
    result["checkpoint_forage_soil"] = checkpoint_forage_soil
    slot_prefix = "IslandSavedHabitat" if habitat_saved else "IslandSharedForage" if meadow_layout == "Shared" else "IslandNursery"
    if checkpoint_drift:
        slot_prefix = "IslandDriftForage"
    if checkpoint_forage_soil:
        slot_prefix = "IslandLocalForageSoil" if "-EcoIslandCheckpointLocalForageSoil" in command.split() else "IslandForageSoil"
    if "-EcoIslandCheckpointFinalBank" in command.split():
        slot_prefix = "IslandFinalBank"
    if "-EcoIslandVerifySnowStageBounds" in command.split() and checkpoint and "-EcoIslandCheckpointFinalBank" in command.split():
        slot_prefix = "IslandSnowBounds"
    if "-EcoIslandVerifyGrasslandStageBounds" in command.split() and checkpoint and "-EcoIslandCheckpointFinalBank" in command.split():
        slot_prefix = "IslandGrassBounds"
    checkpoint_run = re.search(r"(?:^|\s)-EcoIslandCheckpointRun=([A-Za-z0-9_]{1,24})(?:\s|$)", command)
    result["checkpoint_slot"] = f"{slot_prefix}_{seed}" + (f"_{checkpoint_run[1]}" if checkpoint_run else "")
started = time.monotonic()
next_sample = 0.
next_water_sample = 0.
next_feeding_sample = 0.
water_ids = set()
water_targets = {}
water_patches = []
camera = None
origin = u.Vector(*authored["river_view"])


def finish():
    if rifle_combat_trial and not result["errors"]:
        trial = result.get("combat_carrion", {})
        if combat_trial == "Rifle" and trial.get("release_hp") != 0:
            result["errors"].append("Rifle trial target did not reach zero HP")
        if combat_trial == "RiflePresent" and (
                trial.get("release_hp") != 100. or trial.get("shots") or trial.get("damage")):
            result["errors"].append("No-fire rifle control did not preserve the target without damage")
    if local_soil_trial and not result["errors"] and not result.get("checkpoint_mode"):
        trial = result.get("local_forage_soil", {})
        names = set(trial.get("tracked_patches", ()))
        if len(names) != 5 or len(trial.get("rain_events", ())) != 3 or not all(
                names <= row.get("forage_soil_moisture", {}).keys() for row in result["samples"]):
            result["errors"].append("Local soil trial did not cover the five rule-only forage patches through drawdown")
    if result.get("transition_region_trial") and not result["errors"] and not result.get("transition_founder_trial"):
        events = {(agent["stable_id"], event["time"], event["region"], event["reason"])
                  for sample in result["samples"] for agent in sample.get("agents", ())
                  for event in agent.get("gameplay_reason_history", ())
                  if event["reason"] in ("PassageTransitEntered", "PassageArrived")}
        result["transition_events"] = sorted(events, key=lambda event: (event[1], int(event[0])))
        if result.get("transition_habitat"):
            stock_rows = [sample["stocks"] for sample in result["samples"]]
            result["transition_habitat_meals"] = sorted({
                (agent["stable_id"], agent["species"], event["time"], event["amount"])
                for sample in result["samples"] for agent in sample.get("agents", ())
                for event in agent.get("gameplay_reason_history", ())
                if event["reason"] == "HabitatPatchEaten" and event["region"] == result["transition_authoring"]["region_id"]
            })
            result["transition_habitat_stock"] = [row["IslandTransitionForbs"] for row in stock_rows]
            first = stock_rows[0]
            if abs(sum(first.values()) - 215.) > .01 or abs(first["IslandTransitionForbs"] + first["IslandForageWestForbs"] - 9.) > .01:
                result["errors"].append("Transition habitat changed the initial authored food budget")
            if result.get("transition_habitat_founder") and not any(
                    int(meal[0]) == result["transition_rabbit"] for meal in result["transition_habitat_meals"]):
                result["errors"].append("Existing jackrabbit did not feed in the transition habitat")
    if result.get("transition_founder") and not result["errors"] and result.get("transition_checkpoint") != "Save":
        founder = result["transition_founder"]
        events = {(e["time"], e["region"], e["reason"]) for row in founder.get("track", ()) for e in row["reasons"]}
        founder["events"] = sorted(events)
        entered = [t for t, _, reason in events if reason == "PassageTransitEntered"]
        arrived = [t for t, region, reason in events if region == "Riverbank" and reason == "PassageArrived"]
        if result.get("transition_blocked_exit") or result.get("transition_wall"):
            ledger = result.get("transition_ledger", [])
            returned = [t for t, region, reason in events if region == "Highland" and reason == "PassageArrived"]
            if entered or arrived or len(returned) != 1:
                result["errors"].append("Founder did not return to Highland exactly once when the Riverbank route closed")
            if not ledger or ledger[0]["Riverbank"]["incoming_count"] < 1 or ledger[-1]["Riverbank"]["incoming_count"] != 0:
                result["errors"].append("The restored Riverbank reservation was not released")
        elif result["transition_control"]:
            if entered or arrived:
                result["errors"].append("Control founder reached the destination without the transit plan")
        elif result.get("transition_checkpoint") == "Load" and (
                entered or len(arrived) != 1 or arrived[0] <= result["transition_checkpoint_state"]["entered_at"]):
            result["errors"].append("Restored founder did not arrive exactly once without re-entering the corridor")
        elif result.get("transition_checkpoint") != "Load" and (
                len(entered) != 1 or len(arrived) != 1 or entered[0] >= arrived[0]):
            result["errors"].append("Founder did not complete exactly one two-leg corridor crossing")
        else:
            founder["destination_meals"] = sorted(t for t, region, reason in events
                                                 if region == "Riverbank" and "Eaten" in reason and t >= arrived[0])
            if not founder["destination_meals"]:
                result["errors"].append("Founder arrived without a recorded destination meal")
    if (result.get("record_gameplay_reasons") and not result["errors"] and result.get("checkpoint_mode") != "Save"
            and not result.get("checkpoint_rejected_shifted_rat_mouth")):
        if not any(agent.get("gameplay_reason_history") for sample in result["samples"] for agent in sample["agents"]):
            result["errors"].append("Authority gameplay history was not captured")
    if feeding_track_ids and not result["errors"]:
        tracked = {int(agent["stable_id"]) for frame in result["feeding_track"]["samples"] for agent in frame["agents"]}
        missing = set(feeding_track_ids) - tracked
        if missing:
            result["errors"].append(f"Feeding track did not observe requested IDs: {sorted(missing)}")
    if result.get("audit_vegetation") and not result["errors"]:
        settings = result.get("vegetation_settings", {})
        if (settings.get("map_enables_vegetation") or "-EcoVegetation" in command.split()) and not result["samples"][-1]["vegetation"]:
            result["errors"].append("Enabled vegetation was not available to sample")
    if result.get("rain_pattern") and not result["errors"]:
        events = result["rain_pattern_events"]
        rain_exposure = sum((end["time"] - start["time"]) * start["rain"] for start, end in zip(events, events[1:]))
        result["rain_pattern_exposure"] = rain_exposure
        samples = result["samples"]
        received = [sample.get("vegetation", {}).get("Grassland", {}).get("rain") for sample in samples]
        if abs(rain_exposure - 42.) > .1 or not any(rain is not None and abs(rain - .7) < .01 for rain in received):
            result["errors"].append("Grassland did not receive the planned rain pattern")
        if result.get("regional_rain"):
            applied = [sample["grassland_region_weather"] for sample in samples
                       if "grassland_region_weather" in sample]
            if (not any(abs(state["rainfall"] - .7) < .01 for state in applied)
                    or not any(state["rainfall"] < .01 for state in applied)
                    or any(abs(state["rainfall"] - state["planned_rainfall"]) >= .01
                           or abs(state["temperature"] - 18.) >= .01 for state in applied)):
                result["errors"].append("Regional Grassland weather disagreed with the planned rain pattern")
    if (trial := result.get("player_passage")) and not result["errors"]:
        samples = trial["samples"]
        distance = trial.get("max_forward_cm", 0.)
        if not samples or not any(sample["agents"] for sample in samples):
            result["errors"].append("Player passage did not sample any focal animals")
        if ((player_trial == "Still" and trial.get("max_horizontal_displacement_cm", 0.) > 25.)
                or (player_trial != "Still" and (distance < 1000. or not any(
                    sample["grounded"] and sample["player_speed_cm_per_s"] > 1. for sample in samples)))):
            result["errors"].append(f"Player passage failed movement check: {distance:.1f} cm")
    if (trial := result.get("forage_intent")) and not result["errors"]:
        initial = result["samples"][0]
        if len(initial["population"]) != 16 or sum(initial["population"].values()) != 118 or abs(sum(initial["stocks"].values()) - 215.) > .01:
            result["errors"].append("Forage intent comparison changed the saved island baseline")
        if not any(sample["selected_patch"] for sample in trial["samples"]):
            result["errors"].append("Forage intent comparison did not capture a selected patch")
        if not trial.get("payments"):
            result["errors"].append("Forage intent comparison did not capture a patch payment with resource_id")
        expected = {"Control": 0, "Expired": 1}.get(forage_intent)
        count = len(trial["submissions"])
        if (expected is not None and count != expected) or (expected is None and count < 2):
            result["errors"].append(f"Unexpected forage intent submission count: {count}")
        if forage_intent == "Hold" and (not trial["submissions"] or trial["submissions"][-1]["world_seconds"] < 98.):
            result["errors"].append("Sustained forage request did not reach the end of the comparison window")
    if survey_nursery_depth and not result["errors"]:
        if set(result["nursery_depth_survey"]) != {"early_dry", "late_high", "receding"}:
            result["errors"].append("Nursery depth survey did not reach all three observation windows")
    if nursery_drawdown and not result["errors"]:
        if set(result["nursery_drawdown"]["events"]) != {"before", "lowered", "interrupted", "restored"}:
            result["errors"].append("Nursery drawdown did not complete its three observation windows")
    if nursery_fry and not result["errors"]:
        trial = result["nursery_fry"]
        if (set(trial["events"]) != {"before", "lowered", "restored"} or not trial["samples"]
                or trial["samples"][-1]["world_seconds"] - trial["hatch_observed_world_seconds"] < 20.):
            result["errors"].append("Nursery fry comparison did not capture the full post-hatch window")
    if second_mink_flood and not result["errors"]:
        trial = result.get("second_mink_flood", {})
        if (not trial.get("samples") or ("restored" not in trial
                and not (focused_mink_ramp and "dry_ground_arrival" in trial))):
            result["errors"].append("Second mink flood did not record both rising and falling water")
    if (second_mink_bank_layout or verify_mink_bank_layout) and not result["errors"]:
        agents = [a for sample in result["samples"] for a in sample["agents"] if int(a["stable_id"]) == 111]
        events = {(row["reason"], row["time"]) for agent in agents for row in agent.get("gameplay_reason_history", ())}
        result["second_mink_bank_events"] = [[time, event] for event, time in sorted(events, key=lambda row: row[1])]
        required = {"SwimEnter", "HabitatPatchEaten", "SwimExit", "SwimDryBankReached"}
        if required - {event for event, _ in events}:
            result["errors"].append("Second mink did not complete the measured entry, meal and dry bank return")
        if second_mink_saved_flood:
            flood = result.get("second_mink_flood", {})
            if (not {"rise", "restored"} <= flood.keys()
                    or not flood.get("dry_ground_arrival", {}).get("before_restore")):
                result["errors"].append("Second mink did not reach dry Landscape during the saved high-water trial")
    if (trial := result.get("second_eagle_perch")) and not result["errors"]:
        events = {(agent["stable_id"], event["reason"], event["time"])
                  for sample in result["samples"] for agent in sample["agents"] if agent["species"] == "GoldenEagle"
                  for event in agent.get("gameplay_reason_history", ())
                  if event["reason"] in {"FlightPerchSelected", "FlightPerchArrived"}}
        trial["perch_events"] = sorted(events)
        if trial["added_perch_cm"]:
            point = u.Vector(*trial["added_perch_cm"])
            trial["near_added_perch_ground_samples"] = sorted(
                (agent["stable_id"], sample["time"])
                for sample in result["samples"] for agent in sample["agents"]
                if agent["species"] == "GoldenEagle" and agent["hp"] > 0
                and agent["rule_fauna"]["flight_phase"] == 0
                and (u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"]))) - point).length() <= 60.
            )
    if result.get("meadow_layout") == "Shared" and result["samples"] and not result["errors"]:
        meadow = result["meadow_trial"]["patch"]
        budget = result["patch_budget"][meadow]
        if budget["capacity"] != 12. or result["samples"][0]["stocks"][meadow] != 12.:
            result["errors"].append("Shared access changed the original meadow stock")
    u.unregister_slate_post_tick_callback(handle)
    try:
        (out / "IslandFaunaPIE.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        u.log(f"ECO_ISLAND_FAUNA_PIE errors={result['errors']}")
    except OSError:
        u.log_error(traceback.format_exc())
    finally:
        levels.editor_request_end_play()
        u.SystemLibrary.quit_editor()


def set_camera(world, eye, target):
    if focused_mink_ramp:
        return
    global camera
    if not camera:
        camera = u.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, u.CameraActor, u.Transform())
    camera.set_actor_location(eye, False, True)
    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye, target), False)
    pc = u.GameplayStatics.get_player_controller(world, 0)
    pc.set_view_target_with_blend(camera, 0.)
    for command in ("eco.Creature.Labels 0", "ShowFlag.HUD 0", "ShowFlag.Particles 0"):
        u.SystemLibrary.execute_console_command(world, command)


def capture(world, name):
    if focused_mink_ramp or "-EcoIslandNoCapture" in command.split():
        return
    path = out / (name + ".png")
    u.SystemLibrary.execute_console_command(world, f'HighResShot 1920x1080 filename="{path.as_posix()}"')
    result["capture_files"].append(path.name)


def inspect_water_food(world, runtime, row):
    coordinates = re.findall(r"[XYZ]=([-+\d.eE]+)", row["position"])
    if len(coordinates) != 3:
        return []
    origin = tuple(map(float, coordinates))
    candidates = []
    for index, patch_id, center, region, consumers in water_patches:
        if region != row["region"] or row["species"] not in consumers:
            continue
        stock = runtime.inspect_fauna_habitat_stock(patch_id)
        if isinstance(stock, tuple):
            stock = stock[-1]
        sample = inspect.inspect_fauna_water(world, region, u.Vector(*center), 3.)
        column = None
        if sample:
            bounds, _ = sample
            column = [bounds.x, bounds.y]
        candidates.append({"patch_index": index, "distance_cm": math.dist(origin, center),
                           "stock": stock, "center_z": center[2], "column_cm_at_3cm_clearance": column})
    return candidates


def mink_shore_visibility(world, agents):
    connector = result["mink_connector"]
    bank = u.Vector(*connector["bank"])
    entry = u.Vector(*connector["entry"])
    root = u.Vector(*authored["water_samples"]["Roots"])
    rows = []
    for agent in agents:
        if agent["species"] != "Mink" or agent.get("hp", 0) <= 0:
            continue
        coordinates = re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])
        if len(coordinates) != 3:
            continue
        position = u.Vector(*map(float, coordinates))
        eye = u.Vector(0., 0., 15.)
        hits = {}
        for name, start, end in (("bank_sight", position + eye, bank + eye),
                                 ("entry_to_food", entry, root)):
            ignored = []
            while hit := u.SystemLibrary.line_trace_single_for_objects(
                    world, start, end, [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1],
                    False, ignored, u.DrawDebugTrace.NONE, True):
                data = hit.to_tuple()
                component = data[10]
                actor = data[9]
                detail = {"component": component.get_class().get_name() if component else None,
                          "actor": actor.get_class().get_name() if actor else None}
                hits.setdefault(name, detail)
                if not actor or not isinstance(actor, u.WaterBody) or actor in ignored:
                    hits[f"{name}_beyond_water"] = detail
                    break
                ignored.append(actor)
        rows.append({"agent": agent["stable_id"], "energy_fraction": agent["energy_fraction"],
                     "bank_distance_cm": math.hypot(position.x - bank.x, position.y - bank.y),
                     "first_static_hits": hits})
    return rows


def tick(_):
    global next_sample, next_water_sample, next_feeding_sample
    try:
        duration = population_duration or water_forage_duration
        timeout = max(170., duration / 2. + 90.) if duration else 170.
        if time.monotonic() - started > timeout:
            raise RuntimeError("Island PIE timed out")
        world = editor.get_game_world()
        if not world:
            return
        now = u.GameplayStatics.get_time_seconds(world)
        if combat_trial and combat_start <= now <= combat_start + 30.:
            update_combat_carrion(world, now)
        if population_duration:
            tick_population(world, now)
            return
        if player_trial and 20. <= now <= 43.:
            update_player_passage(world, now)
        if feeding_track_ids and now >= next_feeding_sample:
            sample_feeding_track(world, now)
            next_feeding_sample = now + result["feeding_track"]["interval_seconds"]
        if forage_intent and 20. <= now < (115. if forage_intent == "Hold" else 55.):
            update_forage_intent(world, now)
        if "layout" in result and now >= next_water_sample:
            next_water_sample = now + .25
            runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
            if trial_second_eagle_perch and "second_eagle_perch" in result:
                sample_eagle_perch_approach(world, now)
            if nursery_fry and runtime and runtime.is_runtime_ready():
                sample_nursery_drawdown(world, runtime, now)
            if river_rat_refuge and runtime and runtime.is_runtime_ready() and result.get("river_rat_refuge"):
                sample_river_rat_refuge(world, runtime, now)
            if (second_mink_flood or second_mink_saved_flood) and result.get("second_mink_trial", {}).get("near_start_cm"):
                sample_second_mink_flood(world, runtime, now)
                if focused_mink_ramp:
                    flood = result.get("second_mink_flood", {})
                    if "dry_ground_arrival" in flood or "restored" in flood:
                        result["focused_mink_ramp"] = {"stopped_at_pie_seconds": now,
                                                       "dry_ground_reached_at_high_water": "dry_ground_arrival" in flood}
                        finish()
                        return
            if result.get("near_cover") and "eagle_prey_layout" in result:
                sample_highland_eagle_cover(world, runtime, now)
            for agent in sorted(water_ids):
                row = read_agent(world, agent)
                if not row or row.get("hp", 0) <= 0:
                    continue
                details = row.get("rule_fauna", {})
                target = (details.get("food_patch_index", -1), details.get("blocked_patch_index", -1))
                if water_targets.get(agent) != target:
                    water_targets[agent] = target
                    result["water_target_changes"].append({
                        "time": now, "agent": str(agent), "species": row["species"],
                        "position": row["position"], "energy_fraction": row["energy_fraction"],
                        "patch_index": target[0], "blocked_patch_index": target[1],
                        "candidate_geometry": inspect_water_food(world, runtime, row) if runtime else [],
                    })
        if result.get("rain_pattern"):
            update_rain_pattern(world, now)
        if now < next_sample:
            return
        runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
        if runtime and local_soil_trial:
            update_local_forage_soil_trial(world, runtime, now)
        if runtime and result.get("trial_forage_soil") and "forage_soil_enabled_at" not in result:
            runtime.set_editor_property("use_native_soil_for_fauna_forage", True)
            result["forage_soil_enabled_at"] = now
        if runtime and (forage_guild_trial or forage_guild_west) and "forage_guild_trial" not in result:
            if not audit_label or runtime.is_runtime_ready():
                raise RuntimeError("Forage guild trial requires a labeled PIE before stock initialization")
            if forage_guild_trial and forage_guild_west:
                raise RuntimeError("Forage guild trial changes one patch at a time")
            patch_id = "IslandForageWestMeadow" if forage_guild_west else "IslandForageOpenMeadow"
            patches = list(runtime.get_editor_property("fauna_habitat_patches"))
            meadow, = (patch for patch in patches if str(patch.get_editor_property("id")) == patch_id)
            if meadow.get_editor_property("plant_guild") != u.EcoFaunaPlantGuild.GRASS:
                raise RuntimeError("Forage guild trial requires a saved grass meadow")
            meadow.set_editor_property("plant_guild", u.EcoFaunaPlantGuild.BROWSE)
            runtime.set_editor_property("fauna_habitat_patches", patches)
            result["forage_guild_trial"] = {"patch": patch_id, "from": "GRASS", "to": "BROWSE"}
        if runtime and forage_half_meal and "forage_meal_trial" not in result:
            if not audit_label or runtime.is_runtime_ready() or forage_guild_trial or forage_guild_west:
                raise RuntimeError("Meal-size trial requires a labeled PIE before stock initialization and the saved guild")
            patch_id = "IslandForageWestMeadow"
            patches = list(runtime.get_editor_property("fauna_habitat_patches"))
            meadow, = (patch for patch in patches if str(patch.get_editor_property("id")) == patch_id)
            previous = meadow.get_editor_property("energy_per_meal")
            meadow.set_editor_property("energy_per_meal", previous * .5)
            runtime.set_editor_property("fauna_habitat_patches", patches)
            result["forage_meal_trial"] = {"patch": patch_id, "from": previous, "to": previous * .5}
        if runtime and second_mink_trial is not None and "second_mink_trial" not in result:
            if runtime.is_runtime_ready() or not result.get("verify_saved_shore") or not audit_label:
                raise RuntimeError("Second mink trial needs a saved shore and labeled setup before stock initialization")
            apply_second_mink_shore_trial(world, runtime)
        if runtime and result.get("eagle_prey_trial") and "eagle_prey_layout" not in result:
            if runtime.is_runtime_ready():
                raise RuntimeError("Prey layout must be applied before founder spawning")
            apply_eagle_prey_trial(world, runtime)
        if runtime and rat_refuge_mode and "rat_refuge_trial" not in result:
            if runtime.is_runtime_ready():
                raise RuntimeError("Rat refuge trial needs to run before habitat stock initialization")
            result["rat_refuge_trial"] = apply_rat_refuge_trial(world, runtime, rat_refuge_mode)
        if runtime and river_rat_refuge and "river_rat_refuge" not in result:
            if runtime.is_runtime_ready():
                raise RuntimeError("Riverbank refuge trial must precede stock initialization")
            if river_rat_refuge == "Saved":
                sites = [{"patch_index": index, "center_cm": list(patch.get_editor_property("center").to_tuple()),
                          "configured_mouths_cm": [list(point.to_tuple()) for point in
                                                   patch.get_editor_property("shelter_approach_points")]}
                         for index, patch in enumerate(runtime.get_editor_property("fauna_habitat_patches"))
                         if str(patch.get_editor_property("id")).startswith("IslandRiverRatRefuge")]
                if len(sites) != 2:
                    raise RuntimeError("Expected two Riverbank rat refuges in the saved island")
                if any(len(site["configured_mouths_cm"]) != 2 for site in sites):
                    raise RuntimeError("Saved Riverbank refuges lack their two authored mouths")
                result["river_rat_refuge"] = {"mode": "Saved", "sites": sites, "samples": []}
            else:
                result["river_rat_refuge"] = apply_river_rat_refuge_trial(world, runtime, river_rat_refuge)
        if runtime and result.get("split_food_trial") and "mink_connector" not in result:
            if runtime.is_runtime_ready():
                raise RuntimeError("Split trial must run before habitat stock initialization")
            inspect_mink_shore(world, runtime)
            add_mink_shore_connector(world, runtime)
        if not runtime or not runtime.is_runtime_ready():
            if now > 16.:
                if result["samples"]:
                    raise RuntimeError(f"Island authority stopped during PIE at {now:.2f} s")
                result["water_on_failure"] = {name: str(inspect.inspect_fauna_water(world, authored["river"], u.Vector(*pos), 3.))
                    for name, pos in authored["water_samples"].items()}
                raise RuntimeError("Island authority did not initialize")
            return
        if "-EcoIslandTrialSnowEastBoundary" in command.split() and now >= 12. and "snow_east_boundary" not in result:
            region, = (actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)
                       if str(actor.get_editor_property("region_id")) == "Snowfield")
            bounds = region.get_editor_property("region_bounds")
            center = bounds.get_world_location()
            extent = bounds.get_unscaled_box_extent()
            if abs(bounds.get_world_rotation().yaw) > .01 or abs(bounds.get_world_scale().x - 1.) > .01:
                raise RuntimeError("Snowfield boundary trial requires an axis-aligned unscaled box")
            bounds.set_box_extent(extent + u.Vector(225., 0., 0.), False)
            bounds.set_world_location(center + u.Vector(225., 0., 0.), False, True)
            result["snow_east_boundary"] = {"pie_seconds": now,
                                             "before_east_cm": center.x + extent.x,
                                             "after_east_cm": center.x + extent.x + 450.}
        if (stage_bounds_trial or any(flag in command.split() for flag in (
                "-EcoIslandTrialNativeStageBounds", "-EcoIslandTrialSnowStageBounds",
                "-EcoIslandTrialSeparatedStageBounds", "-EcoIslandTrialGrasslandStageBounds"))
                ) and now >= 12. and "native_stage_bounds" not in result:
            result["native_stage_bounds"] = compare_native_stage_bounds(world, runtime, now)
        if second_mink_saved_flood and "second_mink_trial" not in result:
            patch, = (p for p in runtime.get_editor_property("fauna_habitat_patches")
                      if str(p.get_editor_property("id")) == "IslandRiverSecondMinkShore")
            landing = patch.get_editor_property("shore_point")
            bank = patch.get_editor_property("dry_bank_point")
            entry = patch.get_editor_property("water_entry_point")
            result["second_mink_trial"] = {"near_start_cm": list(bank.to_tuple()), "candidate": {
                "bank_cm": list(landing.to_tuple()), "entry_cm": list(entry.to_tuple())}}
            # The saved route ends on the dry bank 50 cm beyond the ramp.
            direction = bank - landing
            direction.z = 0.
            direction = direction / direction.length()
            result["second_mink_saved_ramp"] = {"end_cm": list((bank - direction * 50.).to_tuple()),
                                               "direction": list(direction.to_tuple())}
        if land_forage_trial and "lower_river_land_forage" not in result:
            prepare_lower_river_land_forage(world, runtime)
        if survey_second_mink_shore and "second_mink_shore_survey" not in result:
            survey_mink_founder_shore(world, runtime)
        if second_mink_near_start and second_mink_trial is not None and "near_start_cm" not in result["second_mink_trial"]:
            trial = result["second_mink_trial"]
            original = read_agent(world, 111)
            if not original or original["species"] != "Mink":
                raise RuntimeError("Expected the second mink at startup")
            start = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", original["position"])))
            bank = u.Vector(*trial["candidate"]["bank_cm"])
            geometry = u.EcoCreatureAnimationBuilder
            point = geometry.project_placement_point(world, start + (bank - start) * .65)
            if point is None or not geometry.validate_fauna_ground_segment(world, authored["river"], "Mink", point, bank, 1.):
                raise RuntimeError("Near mink start has no verified ground approach")
            if not geometry.set_island_audit_founder_placement(runtime, 111, authored["river"], point):
                raise RuntimeError("Authority rejected the near mink founder placement")
            trial["near_start_cm"] = list(point.to_tuple())
        if result.get("eagle_fixed_ids") and "eagle_prey_layout" not in result:
            apply_eagle_fixed_id_trial(world, runtime)
        if result.get("survey_seams") and "region_seams" not in result:
            result["region_seams"] = survey_region_seams(world)
        if (result["grassland_passage_trial"] or result["grassland_passage_saved"]) and "grassland_passage" not in result:
            result["grassland_passage"] = inspect_grassland_passage(world, runtime)
        if result.get("transition_region_trial") and "transition_region" not in result:
            if result.get("highland_approach_trial"):
                route, = (actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoHerdMigrationRoute)
                          if str(actor.get_editor_property("from_region")) == "Highland"
                          and str(actor.get_editor_property("to_region")) == result["transition_authoring"]["region_id"])
                points = list(route.get_editor_property("points"))
                route.set_editor_property("points", extend_highland_approach(world, points))
                if not route.is_valid_route():
                    raise RuntimeError("The Highland route rejected the additional approach")
            result["transition_region"] = inspect_transition_region(world, runtime)
            if result.get("transition_founder_trial") and result.get("transition_checkpoint") != "Load":
                place_transition_founder(world, runtime)
            if result.get("transition_habitat_founder"):
                place_transition_rabbit(world, runtime)
            if result.get("transition_habitat_moist"):
                apply_transition_habitat_weather(world)
        if result.get("transition_rabbit") and now >= 5. and not result.get("transition_rabbit_shortage"):
            apply_transition_shortage(world, "Riverbank")
            result["transition_rabbit_shortage"] = True
        if result.get("transition_habitat_saved"):
            sample_saved_transition_habitat(world, runtime, now)
        elif result.get("transition_habitat_river_weather"):
            sample_transition_river_weather(world, now)
        if (result.get("transition_founder") and result.get("transition_checkpoint") != "Load"
                and now >= 5. and "pressure" not in result["transition_founder"]):
            apply_transition_shortage(world)
        if result.get("transition_checkpoint") and "transition_checkpoint_state" not in result:
            if check_transition_checkpoint(world, runtime, now):
                finish()
                return
        if result.get("cover_trial") and "highland_cover" not in result:
            result["highland_cover"] = survey_highland_cover(world, runtime)
        if "-EcoIslandEagleGeometry" in command.split() and "eagle_geometry" not in result:
            result["eagle_geometry"] = survey_eagle_geometry(world, runtime)
        if result.get("survey_highland") and "highland_ground" not in result:
            result["highland_ground"] = survey_highland_ground(world, runtime)
        if result.get("meadow_layout") and "meadow_trial" not in result:
            result["meadow_trial"] = compare_meadow_placement(world, runtime)
        if ("-EcoIslandGrasslandForageLink" in command.split() or "-EcoIslandGrasslandForageLink=Forbs" in command.split()
            ) and "grassland_forage_link" not in result:
            result["grassland_forage_link"] = compare_grassland_forage_link(world, runtime)
        if result.get("eagle_perch_trial") and "eagle_perches" not in result:
            add_eagle_perch_trial(world, runtime)
        if result.get("verify_eagle_perch") and "eagle_perches" not in result:
            result["eagle_perches"] = [list(site.get_editor_property("location").to_tuple())
                                       for site in runtime.get_editor_property("fauna_perches")
                                       if str(site.get_editor_property("species_id")) == "GoldenEagle"]
            if not result["eagle_perches"]:
                raise RuntimeError("No golden eagle perch in the saved island")
            for coordinates in result["eagle_perches"]:
                point = u.Vector(*coordinates)
                projected = u.EcoCreatureAnimationBuilder.project_placement_point(world, point)
                if projected is None or (projected - point).length() > 10.:
                    raise RuntimeError(f"Saved eagle perch has no landing surface at {point}")
            if trial_second_eagle_perch:
                try_second_eagle_perch(world, runtime)
        if result.get("verify_saved_shore") and "saved_mink_shore" not in result:
            patches = {str(p.get_editor_property("id")): p for p in runtime.get_editor_property("fauna_habitat_patches")}
            patch, root = (patches[name] for name in ("IslandRiverRootsShore", "IslandRiverRoots"))
            if not patch.get_editor_property("has_shore_entry"):
                raise RuntimeError("Saved shore entry was not active during initialization")
            center = root.get_editor_property("center")
            entry = patch.get_editor_property("water_entry_point")
            for i in range(41):
                if not inspect.inspect_fauna_water(world, authored["river"], center + (entry - center) * (i / 40.), 6.):
                    raise RuntimeError(f"Saved shore connector lacks water at sample {i}")
            result["saved_mink_shore"] = {key: list(patch.get_editor_property(key).to_tuple())
                                         for key in ("center", "shore_point", "water_entry_point")}
            authored["water_samples"]["RootsShore"] = result["saved_mink_shore"]["center"]
        if survey_forage_water and "forage_water_survey" not in result:
            result["forage_water_survey"] = survey_forage_water_connection(world, runtime)
        if result.get("shore_rain_trial"):
            sample_shore_rain(world, runtime, now)
        if nursery_drawdown:
            sample_nursery_drawdown(world, runtime, now)
        if survey_nursery_depth:
            for label, start in (("early_dry", 25.), ("late_high", 190.), ("receding", 240.)):
                if now >= start and label not in result["nursery_depth_survey"]:
                    result["nursery_depth_survey"][label] = sample_nursery_depth(world, runtime, now)
        if water_forage_split and "water_forage_split_verified" not in result:
            trial = result["water_forage_split"]
            point = u.Vector(*trial["center_cm"])
            water = inspect.inspect_fauna_water(world, authored["river"], point, 3.)
            stock = runtime.inspect_fauna_habitat_stock(trial["patch"])
            if not water or not water[0].x + 3. < point.z < water[0].y - 3. or stock is None:
                raise RuntimeError("Trial gravel patch failed water or stock initialization")
            result["water_forage_split_verified"] = True
        if water_forage_duration == 720 and "water_forage_dilation" not in result:
            u.GameplayStatics.set_global_time_dilation(world, 4.)
            result["water_forage_dilation"] = u.GameplayStatics.get_global_time_dilation(world)
        if survey_water_forage:
            surveys = result.setdefault("water_forage_survey", {})
            for label, start in (("early_dry", 25.), ("late_high", 190.), ("receding", 240.)):
                if now >= start and label not in surveys:
                    surveys[label] = sample_water_forage(world, runtime, now)
        if result.get("checkpoint_mode"):
            if check_island_checkpoint(world, runtime, now):
                finish()
                return
        if result.get("split_food_trial") and not result["validate_shore_on_start"] and not result.get("split_shore_applied"):
            connector = result["mink_connector"]
            patches = [p.copy() for p in runtime.get_editor_property("fauna_habitat_patches")]
            near, = (p for p in patches if str(p.get_editor_property("id")) == "IslandRiverRootsShore")
            near.set_editor_property("has_shore_entry", True)
            near.set_editor_property("shore_point", u.Vector(*connector["bank"]))
            near.set_editor_property("water_entry_point", u.Vector(*connector["entry"]))
            runtime.set_editor_property("fauna_habitat_patches", patches)
            result["split_shore_applied"] = True
        if result.get("layout") in {"shelf", "roots", "inlet"} and "moved_patch" not in result:
            move_trial_patch(runtime)
        if result.get("layout") == "saved" and "saved_patch_center" not in result:
            shelf, = (patch for patch in runtime.get_editor_property("fauna_habitat_patches")
                      if str(patch.get_editor_property("id")) == "IslandRiverSlowShelf")
            actual = shelf.get_editor_property("center")
            expected = u.Vector(*authored["water_samples"]["InletPlants"]) + u.Vector(0., 0., deep_shelf_offset_cm)
            if (actual - expected).length() > .01:
                raise RuntimeError(f"Saved PIE shelf position differs from tested placement: {actual}")
            authored["water_samples"]["SlowShelf"] = [actual.x, actual.y, actual.z]
            result["saved_patch_center"] = [actual.x, actual.y, actual.z]
        if result.get("shore_profile_requested") and "shore_profile" not in result:
            inspect_mink_shore(world, runtime)
            if result.get("connector_trial"):
                add_mink_shore_connector(world, runtime)
        population, fish, river_native, agents = Counter(), {}, [], []
        current_water_ids = set()
        aquatic = {"AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
        for agent in inspect.get_authority_agent_ids(world):
            row = read_agent(world, agent)
            if row:
                if "layout" in result:
                    agents.append(row)
                kind = row.get("species", "unknown")
                if row.get("hp", 0) > 0:
                    population[kind] += 1
                    if kind in water_species and "layout" in result:
                        current_water_ids.add(agent)
                    if kind in ("Herbivore", "Wolf") and row.get("region") == authored["river"]:
                        river_native.append(str(agent))
                    if kind in aquatic:
                        fish[str(agent)] = row.get("position")
                if row.get("brain") and kind == "Herbivore":
                    result["deer_brain"] = row["brain"]
        if "layout" in result:
            water_ids.clear()
            water_ids.update(current_water_ids)
        water = {}
        for name, pos in authored["water_samples"].items():
            sample = inspect.inspect_fauna_water(world, authored["river"], u.Vector(*pos), 3.)
            if sample:
                bounds, flow = sample
                water[name] = [bounds.y - bounds.x, flow.length()]
        stocks = {}
        patches = runtime.get_editor_property("fauna_habitat_patches")
        for patch in patches:
            key = str(patch.get_editor_property("id"))
            stock = runtime.inspect_fauna_habitat_stock(key)
            if stock is not None:
                stocks[key] = float(stock[-1] if isinstance(stock, tuple) else stock)
        if "layout" in result and "patch_budget" not in result:
            result["patch_order"] = [str(patch.get_editor_property("id")) for patch in patches]
            result["active_habitat_stage"] = runtime.get_editor_property("fauna_habitat_stage")
            for index, patch in enumerate(patches):
                if patch.get_editor_property("submerged"):
                    center = patch.get_editor_property("center")
                    water_patches.append((index, result["patch_order"][index], (center.x, center.y, center.z),
                                          str(patch.get_editor_property("region_id")),
                                          {str(species) for species in patch.get_editor_property("consumers")}))
            result["patch_budget"] = {
                str(patch.get_editor_property("id")): {
                    "region": str(patch.get_editor_property("region_id")),
                    "consumers": sorted(str(consumer) for consumer in patch.get_editor_property("consumers")),
                    "capacity": patch.get_editor_property("capacity"),
                    "stage": patch.get_editor_property("stage"),
                    "plant_guild": str(patch.get_editor_property("plant_guild")),
                    "regrowth_per_second": patch.get_editor_property("regrowth_per_second"),
                    "dry_loss_per_second": patch.get_editor_property("plant_dry_loss_per_second"),
                    "energy_per_meal": patch.get_editor_property("energy_per_meal"),
                    "submerged": patch.get_editor_property("submerged"),
                    "nursery": patch.get_editor_property("aquatic_nursery"),
                    "sheltered_species": str(patch.get_editor_property("sheltered_species")),
                    "shelter_radius_cm": patch.get_editor_property("shelter_radius"),
                    "entrance_radius_cm": patch.get_editor_property("entrance_radius"),
                }
                for patch in patches
            }
        result["samples"].append({"time": now, "population": population, "fish": fish, "water": water, "stocks": stocks,
                                  "river_native": river_native})
        if land_forage_trial:
            trial = result["lower_river_land_forage"]
            feeder = next((a for a in agents if str(a["stable_id"]) == str(trial["agent_id"]) and any(
                e["reason"] == "HabitatPatchEaten" and e.get("resource_id") == trial["patch"]
                and 0. <= now - e["time"] < 5. for e in a.get("gameplay_reason_history", ()))), None)
            if trial["extra_access_cm"] and feeder and "IslandFauna_SouthBrowseMeal.png" not in result["capture_files"]:
                point = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", feeder["position"])))
                set_camera(world, point + u.Vector(-520., -380., 320.), point + u.Vector(0., 0., 100.))
                capture(world, "IslandFauna_SouthBrowseMeal")
            if now >= 160.:
                result["samples"][-1]["agents"] = agents
                finish()
                return
        if result.get("regional_rain") or local_soil_trial:
            result["samples"][-1]["forage_soil_moisture"] = sample_forage_soil(runtime, stocks)
        if local_soil_trial:
            result["samples"][-1]["local_forage_soil_weather"] = {
                name: actor.get_environment_state().get_editor_property("rainfall")
                for name, actor in local_soil_weather_regions.items()}
        state = u.GameplayStatics.get_game_state(world)
        if state:
            summary = state.get_ecology_summary()
            if summary.get_editor_property("revision") > 0:
                clock = summary.get_editor_property("time")
                phase = clock.get_editor_property("day_cycle")
                result["samples"][-1]["completed_clock"] = {
                    "authority_seconds": clock.get_editor_property("server_time_seconds"),
                    "phase": str(phase.get_editor_property("phase")).split(".")[-1].split(":")[0].rstrip(">").lower(),
                    "phase_start_seconds": phase.get_editor_property("phase_start_seconds"),
                    "phase_end_seconds": phase.get_editor_property("phase_end_seconds"),
                }
        if result.get("regional_rain") and rain_pattern_region is not None:
            state = rain_pattern_region.get_environment_state()
            result["samples"][-1]["grassland_region_weather"] = {
                "planned_rainfall": result["rain_pattern_events"][-1]["rain"],
                "rainfall": state.get_editor_property("rainfall"),
                "temperature": state.get_editor_property("temperature"),
                "humidity": state.get_editor_property("humidity"),
            }
        if result.get("audit_vegetation"):
            if "vegetation_settings" not in result:
                profile = runtime.get_editor_property("natural_habitat_profile")
                result["vegetation_settings"] = {
                    "map_enables_vegetation": runtime.get_editor_property("enable_vegetation"),
                    "map_enables_life": runtime.get_editor_property("enable_ecosystem_life"),
                    "default_profile": profile.get_path_name() if profile else None,
                    "profile_overrides": sorted(str(region) for region in runtime.get_editor_property("region_habitat_profiles")),
                }
            result["samples"][-1]["vegetation"] = sample_vegetation(world)
        if "layout" in result:
            result["samples"][-1]["agents"] = agents
        if result.get("transition_founder"):
            found = next((a for a in agents if int(a["stable_id"]) == result["transition_founder"]["id"]), None)
            if found:
                result["transition_founder"].setdefault("track", []).append({
                    "time": now, "region": found["region"], "position": found["position"], "hp": found["hp"],
                    "reasons": [e for e in found.get("gameplay_reason_history", ())
                                if e["reason"] in ("PassageTransitEntered", "PassageArrived", "HabitatPatchEaten", "PlantsEaten")],
                })
            if result.get("transition_checkpoint") == "Load" and "transition_checkpoint_state" in result:
                result.setdefault("transition_ledger", []).append(transition_region_ledger(world))
        if result.get("meadow_layout"):
            result["samples"][-1]["meadow_targets"] = {
                agent["stable_id"]: agent["rule_fauna"].get("food_patch_index")
                for agent in agents if agent["species"] in ("Horse", "Buffalo") and "rule_fauna" in agent
            }
        if "mink_connector" in result:
            result["samples"][-1]["mink_shore_visibility"] = mink_shore_visibility(world, agents)
        count = len(result["samples"])
        feeder = None
        if result.get("transition_habitat_river_approach") and "IslandFauna_TransitionMeal.png" not in result["capture_files"]:
            feeder = next((a for a in agents if a["region"] == result["transition_authoring"]["region_id"]
                           and any(e["reason"] == "HabitatPatchEaten" and 0. <= now - e["time"] <= 5.
                                   for e in a.get("gameplay_reason_history", ()))), None)
        if feeder:
            point = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", feeder["position"])))
            set_camera(world, point + u.Vector(-150., -95., 75.), point + u.Vector(0., 0., 18.))
            capture(world, "IslandFauna_TransitionMeal")
        elif count in (11, 12) and "grassland_passage" in result:
            center = u.Vector(*result["grassland_passage"]["center_cm"])
            if count == 11:
                set_camera(world, center + u.Vector(2500., 4500., 7000.), center)
            else:
                capture(world, "IslandFauna_GrasslandPassage")
        elif count == 2:
            u.SystemLibrary.execute_console_command(world, "showhud")
            set_camera(world, origin + u.Vector(-2100., -3600., 4200.), origin + u.Vector(2600., 850., 0.))
        elif count == 3 and result.get("transition_region_trial"):
            center = u.Vector(*result["transition_authoring"]["center_cm"])
            set_camera(world, center + u.Vector(2800., -6500., 10500.), center)
        elif count == 4 and result.get("transition_region_trial"):
            capture(world, "IslandFauna_TransitionTerrain")
        elif count == 5 and result.get("transition_region_trial"):
            set_camera(world, origin + u.Vector(-2100., -3600., 4200.), origin + u.Vector(2600., 850., 0.))
        elif count == 7:
            capture(world, "IslandFauna_RiverAndLake")
        elif count == 8:
            if result.get("verify_saved_shore"):
                edge = u.Vector(*result["saved_mink_shore"]["shore_point"])
                set_camera(world, edge + u.Vector(-510., 110., 450.), edge + u.Vector(85., 95., 0.))
            else:
                edge = u.Vector(*authored["river_shore_view"])
                set_camera(world, edge + u.Vector(-1250., -1500., 480.), edge + u.Vector(900., 850., 35.))
        elif count == 13:
            capture(world, "IslandFauna_MinkShore" if result.get("verify_saved_shore") else "IslandFauna_Riverbank")
        elif count == 14:
            drift = u.Vector(*authored["water_samples"]["Drift"])
            set_camera(world, drift + u.Vector(-510., 55., 10.), drift + u.Vector(430., 120., -25.))
        elif count == 18:
            capture(world, "IslandFauna_Underwater")
        elif count == 19:
            point = u.Vector(*authored["dry_refuges"][2])
            set_camera(world, point + u.Vector(-1500., 950., 850.), point + u.Vector(1350., 650., 0.))
        elif count == 22:
            capture(world, "IslandFauna_Grassland")
        elif count == 23 and not verify_mink_bank_layout:
            if result.get("eagle_perches"):
                point = u.Vector(*result["eagle_perches"][0])
                set_camera(world, point + u.Vector(650., 800., 430.), point)
            else:
                point = u.Vector(*authored["dry_refuges"][-2])
                set_camera(world, point + u.Vector(-1000., -1600., 750.), point + u.Vector(1600., 800., 0.))
        elif count == 26 and not verify_mink_bank_layout:
            capture(world, "IslandFauna_Highland")
        elif count >= 27 and (count - 27) % 4 == 0 and (count - 27) // 4 < len(authored["lake_views"]):
            index = (count - 27) // 4
            eye, target = authored["lake_views"][index]
            set_camera(world, u.Vector(*eye), u.Vector(*target))
        elif count >= 30 and (count - 30) % 4 == 0 and (count - 30) // 4 < len(authored["lake_views"]):
            capture(world, f"IslandFauna_Lake{(count - 30) // 4 + 1}")
        if (result.get("deep_shelf_start") or nursery_fry) and count in (43, 44):
            shelf_point = u.Vector(*result["saved_patch_center"])
            if count == 43:
                set_camera(world, shelf_point + u.Vector(-140., 55., 42.), shelf_point)
            else:
                capture(world, "IslandFauna_DeepShelf")
        if (result.get("verify_eagle_perch") and "IslandFauna_EaglePerch.png" not in result["capture_files"]
                and not (verify_mink_bank_layout and count in (22, 23))):
            for agent in agents:
                if agent["species"] != "GoldenEagle" or agent.get("rule_fauna", {}).get("flight_phase") != 0:
                    continue
                arrivals = [e for e in agent.get("gameplay_reason_history", ()) if e["reason"] == "FlightPerchArrived"]
                if not arrivals or now - arrivals[-1]["time"] > 6.:
                    continue
                point = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))
                set_camera(world, point + u.Vector(-330., -230., 250.), point + u.Vector(0., 0., 22.))
                capture(world, "IslandFauna_EaglePerch")
                break
        if verify_mink_bank_layout and count in (22, 23):
            local, = (patch for patch in runtime.get_editor_property("fauna_habitat_patches")
                      if str(patch.get_editor_property("id")) == "IslandRiverSecondMinkShore")
            midpoint = (local.get_editor_property("shore_point") + local.get_editor_property("dry_bank_point")) * .5
            if count == 22:
                set_camera(world, midpoint + u.Vector(320., -360., 210.), midpoint)
            else:
                capture(world, "IslandFauna_SecondMinkBank")
        if (result.get("verify_high_bank") and result.get("shore_rain_trial") and now >= 60.
                and not (verify_mink_bank_layout and count in (22, 23))):
            surface = result["shore_rain"][-1]["surface_z"]
            peak = max(row["surface_z"] for row in result["shore_rain"])
            if surface >= peak - .1 and "IslandFauna_MinkHighWaterExit.png" not in result["capture_files"]:
                bank = u.Vector(*result["saved_mink_shore"]["shore_point"])
                for agent in agents:
                    if agent["species"] != "Mink" or agent.get("rule_fauna", {}).get("swimming"):
                        continue
                    if not any(e["reason"] == "SwimExit" and 0. <= now - e["time"] <= 5.
                               for e in agent.get("gameplay_reason_history", ())):
                        continue
                    point = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))
                    if (point - bank).length() <= 250.:
                        set_camera(world, point + u.Vector(-225., 70., 125.), point)
                        capture(world, "IslandFauna_MinkHighWaterExit")
                        break
        minimum_duration = 240. if result.get("verify_high_bank") and result.get("shore_rain_trial") else 175.
        minimum_duration = max(minimum_duration, water_forage_duration)
        if nursery_fry:
            hatch = result["nursery_fry"].get("hatch")
            minimum_duration = max(minimum_duration, result["nursery_fry"]["hatch_observed_world_seconds"] + 24.) if hatch else 285.
        if now >= max(minimum_duration, (26 + 4 * len(authored["lake_views"])) * 5.):
            first = result["samples"][0]
            if any(row["river_native"] for row in result["samples"]):
                result["errors"].append("Native land animals entered the rules-only river region")
            missing = set().union(*(set(row) for row in authored["founders"].values())) - set(first["population"])
            if missing:
                result["errors"].append(f"Missing initial species {sorted(missing)}")
            if len(water) != len(authored["water_samples"]):
                result["errors"].append(f"Missing valid water columns: {sorted(set(authored['water_samples'])-set(water))}")
            moving = {agent for agent, pos in first["fish"].items()
                      if len({row["fish"].get(agent) for row in result["samples"] if row["fish"].get(agent)}) > 2}
            result["moving_fish"] = len(moving)
            if not moving:
                result["errors"].append("No fish movement detected")
            if result.get("shore_rain_trial"):
                levels = [row["bank_above_surface_cm"] for row in result["shore_rain"]]
                if max(levels) - min(levels) < 23.:
                    result["errors"].append("Rain did not produce the expected water level change")
                if result.get("verify_high_bank"):
                    peak = max(row["surface_z"] for row in result["shore_rain"])
                    at_peak = [row for row in result["shore_rain"] if row["surface_z"] >= peak - .1]
                    exit_times = {event["time"] for sample in result["samples"] for agent in sample["agents"]
                                  if agent["species"] == "Mink" for event in agent.get("gameplay_reason_history", ())
                                  if event["reason"] == "SwimExit"}
                    result["peak_water_exits"] = sorted(t for t in exit_times if any(abs(t - row["time"]) < 2.5 for row in at_peak))
                    if min(levels) <= 0. or not result["peak_water_exits"]:
                        result["errors"].append("Saved high bank did not provide a dry exit at peak water")
                elif min(levels) >= 0. or max(levels) <= 0.:
                    result["errors"].append("Rain did not flood and expose the original mink landing")
            elif result.get("verify_saved_shore"):
                reasons = {event["reason"] for sample in result["samples"] for agent in sample["agents"]
                           if agent["species"] == "Mink" for event in agent.get("gameplay_reason_history", ())}
                if not {"SwimEnter", "SwimExit", "HabitatPatchEaten"} <= reasons:
                    result["errors"].append(f"Missing saved shore behavior: {sorted(reasons)}")
            if result.get("verify_eagle_perch"):
                reasons = {event["reason"] for sample in result["samples"] for agent in sample["agents"]
                           if agent["species"] == "GoldenEagle" for event in agent.get("gameplay_reason_history", ())}
                result["eagle_observed_reasons"] = sorted(reasons)
                # A changed feeding routine can change when an eagle chooses to land.
                # Keep the saved landing-surface check and record its behavior in the trial.
                feeding_routine_trial = bool(feeding_track_ids and meal_match and meal_match[1] == "4")
                if river_rat_refuge:
                    result["unobserved_perch_behavior"] = sorted({"FlightPerchSelected", "FlightPerchArrived"} - reasons)
                elif not (result.get("eagle_prey_trial") or result.get("eagle_fixed_ids") or feeding_routine_trial) and not {"FlightPerchSelected", "FlightPerchArrived"} <= reasons:
                    result["errors"].append(f"Missing saved perch behavior: {sorted(reasons)}")
            if result.get("audit_nursery"):
                hatch_times = {(agent["species"], event["related_id"], event["time"])
                               for sample in result["samples"] for agent in sample["agents"]
                               for event in agent.get("gameplay_reason_history", ()) if event["reason"] == "AquaticHatch"}
                result["aquatic_hatches"] = sorted(hatch_times)
            finish()
            return
        next_sample = now + 5.
    except Exception:
        result["errors"].append(traceback.format_exc())
        finish()


def read_agent(world, agent):
    value = inspect.capture_agent(world, agent)
    raw = next((item for item in value if isinstance(item, str)), "") if isinstance(value, tuple) else value
    return json.loads(raw) if raw else None


def tick_population(world, now):
    if water_forage_shared and "-EcoIslandAuditDriftStock" in command.split() and not result.get("drift_stock_audit"):
        u.SystemLibrary.execute_console_command(world, "eco.Fauna.ForageStockAudit IslandRiverDrift")
        result["drift_stock_audit"] = True
    global next_sample
    runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
    if runtime and "population_uses_forage_soil" not in result:
        enabled = bool(runtime.get_editor_property("use_native_soil_for_fauna_forage"))
        if population_without_forage_soil:
            if runtime.is_runtime_ready() or not enabled:
                raise RuntimeError("Forage soil control needs the enabled saved setting before initialization")
            runtime.set_editor_property("use_native_soil_for_fauna_forage", False)
        result["population_uses_forage_soil"] = enabled and not population_without_forage_soil
    state = u.GameplayStatics.get_game_state(world)
    if not runtime or not runtime.is_runtime_ready() or not state:
        return
    summary = state.get_ecology_summary()
    if summary.get_editor_property("revision") <= 0:
        return
    clock = summary.get_editor_property("time")
    completed = clock.get_editor_property("server_time_seconds")
    if water_forage_shared and "-EcoIslandDriftRainPulse" in command.split():
        update_drift_rain_pulse(world, completed)
    if drift_seasonal_trial:
        update_seasonal_drift_water(world, runtime, completed)
    if drift_visual_trial:
        sample_seasonal_drift_visual(world, runtime, completed)
    if completed < next_sample:
        return
    agents = []
    population = Counter()
    regional = {}
    backends = {}
    for agent_id in inspect.get_authority_agent_ids(world):
        agent = read_agent(world, agent_id)
        if not agent:
            continue
        kind = agent["species"]
        backend = agent.get("brain") or ("RuleFauna" if "rule_fauna" in agent else "Unreported")
        backends.setdefault(kind, set()).add(backend)
        if agent["hp"] > 0.:
            population[kind] += 1
            regional.setdefault(agent["region"], Counter())[kind] += 1
        agents.append({key: agent[key] for key in (
            "stable_id", "species", "region", "position", "energy", "energy_fraction", "hp", "activity", "body_scale",
            "brain", "policy_contract", "gameplay_reason_history", "last_intake") if key in agent})
    if not result["samples"]:
        expected = set().union(*(set(row) for row in authored["founders"].values()))
        if not expected <= population.keys() or len(population) != 16 or sum(population.values()) != 118:
            raise RuntimeError(f"Unexpected island starting roster: {population}")
        result["initial_backends"] = {kind: sorted(values) for kind, values in backends.items()}
        result["population_target_seconds"] = population_duration
        if water_forage_split or water_forage_shared:
            point = u.Vector(*result["water_forage_split"]["center_cm"])
            column = inspect.inspect_fauna_water(world, authored["river"], point, 3.)
            if not column or not column[0].x + 3. < point.z < column[0].y - 3.:
                raise RuntimeError("Population forage comparison requires a submerged, accessible food point")
        result["initial_routes"] = {
            actor.get_actor_label(): bool(actor.get_editor_property("enabled"))
            for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoHerdMigrationRoute)
            if actor.get_editor_property("allow_rule_fauna_passage")
        }
    stocks, capacities = {}, {}
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        name = str(patch.get_editor_property("id"))
        stock = runtime.inspect_fauna_habitat_stock(name)
        if stock is not None:
            stocks[name] = float(stock[-1] if isinstance(stock, tuple) else stock)
            capacities[name] = patch.get_editor_property("capacity")
    day_cycle = clock.get_editor_property("day_cycle")
    phase = str(day_cycle.get_editor_property("phase")).split(".")[-1].split(":")[0].rstrip(">").lower()
    result["samples"].append({
        "time": now, "completed_clock": {"authority_seconds": completed, "phase": phase,
                                         "phase_start_seconds": day_cycle.get_editor_property("phase_start_seconds"),
                                         "phase_end_seconds": day_cycle.get_editor_property("phase_end_seconds")},
        "population": population, "regional_population": regional, "agents": agents, "stocks": stocks,
        "region_food": {str(row.get_editor_property("region_id")): row.get_editor_property("food_amount")
                        for row in summary.get_editor_property("regions")},
        "species_ledger": {str(row.get_editor_property("species_id")): {
            key: row.get_editor_property(key) for key in ("population", "births", "deaths")}
            for row in summary.get_editor_property("species")},
        "vegetation": sample_vegetation(world),
        "forage_soil_moisture": sample_forage_soil(runtime, stocks) if result["population_uses_forage_soil"] else {},
    })
    if len(result["samples"]) == 1:
        if abs(sum(capacities.values()) - 215.) > .01:
            raise RuntimeError("Unexpected initial authored food capacity")
        if water_forage_shared and abs(capacities.get("IslandRiverDrift", 0.) - 11.) > .001:
            raise RuntimeError("Shared Drift access changed the original stock capacity")
        result["authored_capacities"] = capacities
        result["initial_patch_inputs"] = snapshot_population_patch_inputs(runtime)
        u.GameplayStatics.set_global_time_dilation(world, 4.)
        result["population_dilation"] = u.GameplayStatics.get_global_time_dilation(world)
    next_sample = min(population_duration, (math.floor(completed / 30.) + 1) * 30.)
    if completed >= 1800. and not result.get("population_midpoint_reported"):
        result["population_midpoint_reported"] = True
        u.log(f"ECO_ISLAND_POPULATION midpoint={completed:.3f} alive={sum(population.values())}")
    if completed >= population_duration:
        if drift_visual_trial:
            phases = {row["phase"]: row for row in result.get("drift_visual_samples", [])}
            if (set(phases) != {"before", "exposed", "recovered", "late"}
                    or not phases["before"]["submerged"] or phases["exposed"]["submerged"]
                    or not all(phases[name]["submerged"] for name in ("recovered", "late"))
                    or not phases["exposed"]["height_fraction"]
                    < max(phases[name]["height_fraction"] for name in ("recovered", "late"))
                    < phases["before"]["height_fraction"]):
                raise RuntimeError("Expected water exposure, depleted appearance and measurable biomass recovery")
        if drift_surface_trial:
            phases = {row["phase"]: row for row in result["drift_visual_samples"]}
            before = {tuple(row["offset_cm"]): row for row in phases["before"]["surface_profile"]}
            exposed = {tuple(row["offset_cm"]): row for row in phases["exposed"]["surface_profile"]}
            recovered = {tuple(row["offset_cm"]): row for row in phases["recovered"]["surface_profile"]}
            exposed_ground = [
                list(offset) for offset, first in before.items()
                if first["bed_cm"] is not None and exposed[offset]["bed_cm"] is not None
                and recovered[offset]["bed_cm"] is not None
                and abs(first["bed_cm"] - exposed[offset]["bed_cm"]) < .01
                and abs(first["bed_cm"] - recovered[offset]["bed_cm"]) < .01
                and first["render_depth_cm"] > 2. and exposed[offset]["render_depth_cm"] < -2.
                and recovered[offset]["render_depth_cm"] > 2.
                and first["swimmable_at_1cm"] and not exposed[offset]["swimmable_at_1cm"]
                and recovered[offset]["swimmable_at_1cm"]
            ]
            result["drift_surface_exposed_ground_offsets_cm"] = exposed_ground
            if drift_shore_trial and not exposed_ground:
                raise RuntimeError("The Drift shore trial did not create a wet-dry-wet shallow margin")
        finish()


def snapshot_population_patch_inputs(runtime):
    """Capture the normalized runtime definitions once, before the run diverges."""
    scalars = ("stage", "capacity", "regrowth_per_second", "energy_per_meal", "submerged", "aquatic_nursery",
               "has_shore_entry", "shelter_radius", "entrance_radius", "plant_moisture_need",
               "plant_dry_loss_per_second", "track_local_soil_moisture", "seasonal_full_growth_depth_cm",
               "seasonal_dry_loss_per_second")
    labels = ("region_id", "plant_guild", "sheltered_species", "forage_water_habitat_id")
    vectors = ("center", "shore_point", "water_entry_point", "dry_bank_point", "plant_growth_temperature")
    rows = {}
    order = []
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        prop = patch.get_editor_property
        name = str(prop("id"))
        order.append(name)
        row = {field: prop(field) for field in scalars}
        row.update({field: str(prop(field)) for field in labels})
        for field in vectors:
            vector = prop(field)
            row[field] = [vector.x, vector.y, vector.z]
        rain = prop("plant_growth_rainfall")
        row["plant_growth_rainfall"] = [rain.x, rain.y]
        row["consumers"] = sorted(map(str, prop("consumers")))
        row["forage_access_points"] = [[point.x, point.y, point.z] for point in prop("forage_access_points")]
        if mouths := prop("shelter_approach_points"):
            row["shelter_approach_points"] = [[point.x, point.y, point.z] for point in mouths]
        rows[name] = row
    return {"active_stage": runtime.get_editor_property("fauna_habitat_stage"), "patch_order": order, "patches": rows}


def update_forage_intent(world, now):
    trial = result["forage_intent"]
    samples = trial["samples"]
    if samples and now - samples[-1]["world_seconds"] < .25:
        return
    runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
    if not runtime or not runtime.is_runtime_ready():
        return
    agent = read_agent(world, trial["agent_id"])
    if not agent or agent["hp"] <= 0:
        return
    if agent["species"] != "Horse":
        raise RuntimeError("Expected island horse 44")
    state = u.GameplayStatics.get_game_state(world).get_ecology_summary()
    authority_time = state.get_editor_property("time").get_editor_property("server_time_seconds")
    submissions = trial["submissions"]
    refresh_window = {"Alternate": (24., 42.), "Switch": (37., 43.), "Hold": (37., 100.)}.get(forage_intent)
    submit = (forage_intent == "Expired" and not submissions and 20. <= now < 22.) or (
        refresh_window and refresh_window[0] <= now < refresh_window[1]
        and (not submissions or now - submissions[-1]["world_seconds"] >= .75))
    if submit:
        if not runtime.submit_fauna_food_intent(trial["agent_id"], u.EcoFaunaFoodIntent.HABITAT_PATCH,
                                                0, trial["requested_patch"]):
            raise RuntimeError("Authority rejected the saved meadow request")
        submissions.append({"world_seconds": now, "completed_authority_seconds": authority_time})
    patches = result.get("patch_order", ())
    selected = agent["rule_fauna"]["food_patch_index"]
    stock = runtime.inspect_fauna_habitat_stock(trial["requested_patch"])
    samples.append({"world_seconds": now, "completed_authority_seconds": authority_time,
                    "position": agent["position"], "energy": agent["energy"],
                    "requested_patch_stock": stock[-1] if isinstance(stock, tuple) else stock,
                    "selected_patch": patches[selected] if 0 <= selected < len(patches) else None})
    payments = trial.setdefault("payments", [])
    for event in agent.get("gameplay_reason_history", ()):
        if (event["reason"] == "HabitatPatchEaten" and event.get("resource_id")
                and event["time"] >= samples[0]["completed_authority_seconds"] and event not in payments):
            payments.append(event)


def update_player_passage(world, now):
    pawn = u.GameplayStatics.get_player_pawn(world, 0)
    if not pawn:
        return
    trial = result["player_passage"]
    movement = pawn.character_movement
    start = u.Vector(37600., 35750., 3098.59)
    direction = u.Vector(1., 0., 0.)
    if "start" not in trial:
        bridge = pawn.get_component_by_class(u.EcoPlayerEcologyComponent)
        if not bridge:
            raise RuntimeError("Island player ecology component missing")
        runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
        audio = runtime.get_editor_property("footstep_audio_set") if runtime else None
        profiles = dict(audio.get_editor_property("profiles")) if audio else {}
        rabbit = next((profile for name, profile in profiles.items() if str(name) == "Jackrabbit"), None)
        if rabbit is None:
            raise RuntimeError("Island jackrabbit hearing profile missing")
        trial["jackrabbit_hearing_profile"] = {
            "asset": audio.get_path_name(),
            **{key: rabbit.get_editor_property(key) for key in ("hearing_range", "hearing_threshold", "occluded_hearing")},
        }
        ground = u.EcoCreatureAnimationBuilder.project_placement_point(world, start)
        if ground is None:
            raise RuntimeError("No ground at the fixed Riverbank player course")
        for name in ("eco.Cam.BlockMove 0", "eco.Senses.NoiseLog 1", "eco.Footsteps.HearingLog 1"):
            u.SystemLibrary.execute_console_command(world, name)
        bridge.set_editor_property("use_keyboard_gait", False)
        gait_index = {"Still": 0, "Sneak": 1, "Run": 2}[player_trial]
        if not u.EcoCreatureAnimationBuilder.set_audit_player_gait(pawn, gait_index):
            raise RuntimeError(f"The player ecology component rejected gait {player_trial}")
        trial["native_gait_index"] = gait_index
        trial["max_walk_speed_cm_per_s"] = movement.max_walk_speed
        movement.stop_movement_immediately()
        half_height = pawn.capsule_component.get_scaled_capsule_half_height()
        origin = ground + u.Vector(0., 0., half_height + 1.)
        if not pawn.set_actor_location(origin, False, True):
            raise RuntimeError("Player could not start the fixed Riverbank course")
        trial["start"] = list(origin.to_tuple())
    position = pawn.get_actor_location()
    forward = position.x - trial["start"][0]
    trial["max_forward_cm"] = max(forward, trial.get("max_forward_cm", 0.))
    displacement = math.hypot(forward, position.y - trial["start"][1])
    trial["max_horizontal_displacement_cm"] = max(displacement, trial.get("max_horizontal_displacement_cm", 0.))
    if player_trial != "Still" and 22. <= now < 33. and forward < 1100.:
        pawn.add_movement_input(direction, 1., False)
    samples = trial["samples"]
    if samples and now - samples[-1]["world_seconds"] < .25:
        return
    agents = []
    for agent_id in (49, 50, 70, 71):
        row = read_agent(world, agent_id)
        if row:
            agents.append({key: row[key] for key in (
                "stable_id", "species", "position", "region", "hp", "energy", "activity", "sense", "sense_source_key",
                "gameplay_reason_history", "wolf_hunting", "wolf_has_target") if key in row})
    state = u.GameplayStatics.get_game_state(world)
    clock = state.get_ecology_summary().get_editor_property("time")
    samples.append({"world_seconds": now, "completed_authority_seconds": clock.get_editor_property("server_time_seconds"),
                    "player_position_cm": list(position.to_tuple()), "player_speed_cm_per_s": pawn.get_velocity().length(),
                    "grounded": movement.is_moving_on_ground(), "agents": agents})


def update_combat_carrion(world, now):
    pawn = u.GameplayStatics.get_player_pawn(world, 0)
    if pawn is None:
        return
    trial = result.setdefault("combat_carrion", {
        "mode": combat_trial, "start_game_seconds": combat_start, "victim": combat_victim, "damage": [], "press_times": [],
    })
    if trial.get("released"):
        return
    if "player_state" not in trial:
        player_state = pawn.get_editor_property("player_state")
        melee = pawn.get_component_by_class(u.EcoMeleeHitComponent)
        avatar = pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
        if not isinstance(player_state, u.EcoPlayerState) or not melee or not melee.get_editor_property("attack_data") or not avatar:
            raise RuntimeError("Team combat pawn, player state and melee input data are required")
        trial["player_state"] = player_state.get_class().get_name()
        trial["pawn"] = pawn.get_class().get_name()
        player_state.set_invulnerable(True)
        melee.on_damage_outcome.add_callable(record_carrion_damage)
        if rifle_combat_trial:
            fire = pawn.get_component_by_class(u.EcoWeaponFireComponent)
            equipment = pawn.get_component_by_class(u.EcoEquipmentComponent)
            if not fire or not equipment or not equipment.get_editor_property("weapon"):
                raise RuntimeError("Team combat pawn needs its equipped rifle")
            fire.on_damage_outcome.add_callable(record_carrion_damage)
            fire.on_shot.add_callable(record_carrion_shot)
            u.SystemLibrary.execute_console_command(world, "Log LogTemp Verbose")
            pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
    victim = read_agent(world, trial["victim"])
    if now >= combat_start + 24. or not victim or victim["hp"] <= 0.:
        trial["release_hp"] = victim["hp"] if victim else None
        trial["released"] = now
        if rifle_combat_trial:
            avatar = pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
            avatar.release_configured_action(u.load_asset("/Game/JWJ/Weapons/IA_FireRifle"))
            avatar.release_configured_action(u.load_asset("/Game/JWJ/Weapons/IA_AimRifle"))
            u.SystemLibrary.execute_console_command(world, "Log LogTemp Log")
        pawn.set_actor_location(u.Vector(37600., 35750., 15000.), False, True)
        pawn.character_movement.stop_movement_immediately()
        return
    native_position = victim.get("native_world_position")
    position = native_position or [
        float(value) for value in re.findall(r"[XYZ]=([-+\d.eE]+)", victim["position"])]
    target = u.Vector(*position)
    trial["last_live_target_position_cm"] = position
    if rifle_combat_trial:
        update_carrion_rifle(world, pawn, trial, target, now, aim_at_proxy=not native_position)
        return
    ground = next((value for offset in (u.Vector(-35., 0., 0.), u.Vector(0., -35., 0.),
                                        u.Vector(35., 0., 0.), u.Vector(0., 35., 0.))
                   if (value := u.EcoCreatureAnimationBuilder.project_placement_point(world, target + offset)) is not None), None)
    if ground is None:
        ground = target + u.Vector(-35., 0., 0.)
    pawn.set_actor_location(ground + u.Vector(0., 0., pawn.capsule_component.get_scaled_capsule_half_height()), False, True)
    pawn.character_movement.stop_movement_immediately()
    controller = u.GameplayStatics.get_player_controller(world, 0)
    controller.set_view_target_with_blend(pawn, 0.)
    offset = target - ground
    facing = u.Rotator(yaw=math.degrees(math.atan2(offset.y, offset.x)))
    controller.set_control_rotation(facing)
    pawn.set_actor_rotation(facing, True)
    if "first_attack" in trial and now <= combat_start + 4.3:
        hand = pawn.mesh.get_socket_location("Attack_Hand_R")
        proxy_center = u.Vector(*trial["first_attack"]["target_proxy"]) if trial["first_attack"]["target_proxy"] else None
        if proxy_center:
            current_proxy_center = proxy_center + target - u.Vector(*trial["first_attack"]["target_position"])
            trial["closest_hand_to_proxy_cm"] = min(
                trial.get("closest_hand_to_proxy_cm", float("inf")), (hand - current_proxy_center).length())
    presses = trial["press_times"]
    if combat_trial == "Attack" and now >= combat_start + 3. and (not presses or now - presses[-1] >= 1.5):
        if not presses:
            runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
            proxies = u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureHitProxy)
            visuals = u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor)
            trial["first_attack"] = {
                "active_proxies": runtime.get_combat_diagnostics().active_proxies,
                "target_visual_bound": any(actor.get_editor_property("visual_state").alive
                                      and actor.get_editor_property("visual_state").stable_agent_id == trial["victim"]
                                      for actor in visuals),
                "target_proxy": next((list(proxy.get_actor_location().to_tuple()) for proxy in proxies
                                      if proxy.get_editor_property("stable_agent_id") == trial["victim"]), None),
                "target_position": list(target.to_tuple()),
                "player_position": list(pawn.get_actor_location().to_tuple()),
            }
        action = u.load_asset("/Game/Variant_Combat/Input/Actions/IA_ComboAttack")
        avatar = pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
        avatar.release_configured_action(action)
        avatar.press_configured_action(action)
        presses.append(now)


def record_carrion_damage(value):
    result["combat_carrion"]["damage"].append({
        "result": str(value.result), "target": str(value.target_stable_agent_id), "step": value.step_id,
        "applied": value.applied_damage, "hp": value.remaining_hp,
    })


def update_carrion_rifle(world, pawn, trial, target, now, aim_at_proxy):
    pawn.set_actor_location(target + u.Vector(-650., 0., 96.), False, True)
    pawn.character_movement.stop_movement_immediately()
    controller = u.GameplayStatics.get_player_controller(world, 0)
    controller.set_view_target_with_blend(pawn, 0.)
    camera = pawn.get_component_by_class(u.CameraComponent)
    avatar = pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
    aim = pawn.get_component_by_class(u.EcoAimComponent)
    if not trial.get("aim_requested"):
        avatar.press_configured_action(u.load_asset("/Game/JWJ/Weapons/IA_AimRifle"))
        trial["aim_requested"] = True
    point = target + u.Vector(0., 0., 45.)
    if aim_at_proxy:
        proxy = next((actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureHitProxy)
                      if actor.get_editor_property("stable_agent_id") == combat_victim), None)
        if proxy:
            point = proxy.get_actor_location()
    controller.set_control_rotation(u.MathLibrary.find_look_at_rotation(camera.get_world_location(), point))
    presses = trial["press_times"]
    if combat_trial == "Rifle" and aim.get_editor_property("aiming") and now >= combat_start + 3. and (
            not presses or now - presses[-1] >= .6):
        action = u.load_asset("/Game/JWJ/Weapons/IA_FireRifle")
        avatar.release_configured_action(action)
        avatar.press_configured_action(action)
        presses.append(now)


def record_carrion_shot(execution, muzzle, end):
    result["combat_carrion"].setdefault("shots", []).append({
        "execution": execution, "distance_cm": (end - muzzle).length(),
    })


def sample_feeding_track(world, now):
    game_state = u.GameplayStatics.get_game_state(world)
    if not game_state:
        return
    summary = game_state.get_ecology_summary()
    if summary.get_editor_property("revision") <= 0:
        return
    completed_time = summary.get_editor_property("time")
    rows = []
    for agent_id in feeding_track_ids:
        agent = read_agent(world, agent_id)
        if agent:
            rows.append({key: agent[key] for key in ("stable_id", "species", "hp", "energy", "energy_fraction", "activity",
                                                     "position", "region", "gameplay_reason_history",
                                                     "last_plant_intake", "presentation_eating", "native_food_cell",
                                                     "native_food_remaining", "native_food_probe") if key in agent})
    result["feeding_track"]["samples"].append({
        "world_seconds": now,
        "completed_authority_seconds": completed_time.get_editor_property("server_time_seconds"),
        "agents": rows,
    })


def sample_forage_soil(runtime, patch_ids):
    moisture = {}
    for key in patch_ids:
        soil = runtime.inspect_fauna_forage_soil_moisture(key)
        if soil is not None:
            moisture[key] = float(soil[-1] if isinstance(soil, tuple) else soil)
    return moisture


def survey_forage_water_connection(world, runtime):
    habitats = [actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
                if actor.is_valid_habitat() and actor.get_editor_property("connected_fresh_water")
                and actor.get_editor_property("supports_fauna_swimming")]
    rows = {}
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        region = str(patch.get_editor_property("region_id"))
        if patch.get_editor_property("submerged") or region not in {authored["river"], "ZHighlandRiverTransition"}:
            continue
        center = patch.get_editor_property("center")
        sites = []
        for habitat in habitats:
            bounds = habitat.get_editor_property("bounds")
            transform, extent = bounds.get_world_transform(), bounds.get_unscaled_box_extent()
            local = u.MathLibrary.inverse_transform_location(transform, center)
            closest = u.MathLibrary.transform_location(transform, u.Vector(
                min(extent.x, max(-extent.x, local.x)), min(extent.y, max(-extent.y, local.y)), local.z))
            distance = math.hypot(center.x - closest.x, center.y - closest.y)
            sites.append((habitat, {"habitat": str(habitat.get_editor_property("habitat_id")),
                          "water_region": str(habitat.get_editor_property("region_id")),
                          "horizontal_gap_to_authored_bounds_cm": distance,
                          "root_inside_volume": (abs(local.x) <= extent.x and abs(local.y) <= extent.y
                                                 and abs(local.z) <= extent.z),
                          "root_above_base_surface_cm": center.z - habitat.get_editor_property("water_surface_z"),
                          "authored_rain_rise_cm": habitat.get_editor_property("water_rain_rise_cm"),
                          "authored_periodic_rise_cm": habitat.get_editor_property("water_level_rise")}))
        sites.sort(key=lambda entry: (entry[1]["horizontal_gap_to_authored_bounds_cm"], entry[1]["habitat"]))
        nearby = []
        for habitat, site in sites[:3]:
            center_water = habitat.get_actor_location()
            center_water.z = habitat.get_editor_property("water_surface_z") - 20.
            water = inspect.inspect_fauna_water(world, site["water_region"], center_water, 1.)
            if water:
                bottom, surface = water[0].to_tuple()
                site["center_water_column_cm"] = [bottom, surface]
                site["root_above_observed_center_surface_cm"] = center.z - surface
            nearby.append(site)
        rows[str(patch.get_editor_property("id"))] = {"region": region, "center_cm": list(center.to_tuple()),
            "nearby_water_volumes": nearby}
    if not rows or not habitats:
        raise RuntimeError("Expected connected freshwater volumes and rules-only land forage")
    return rows


def prepare_lower_river_land_forage(world, runtime):
    geometry = u.EcoCreatureAnimationBuilder
    region = authored["river"]
    patch_id = "IslandForageSouthBrowse"
    patch, = (p for p in runtime.get_editor_property("fauna_habitat_patches")
              if str(p.get_editor_property("id")) == patch_id)
    root = patch.get_editor_property("center")
    habitat, = (a for a in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
                if str(a.get_editor_property("habitat_id")) == "IslandLowerRiver05")
    surface = habitat.get_editor_property("water_surface_z")
    species = sorted(str(kind) for kind in patch.get_editor_property("consumers"))

    def check(start):
        return {kind: {str(scale): {
            "to_patch": geometry.validate_fauna_ground_segment(world, region, kind, start, root, scale),
            "from_patch": geometry.validate_fauna_ground_segment(world, region, kind, root, start, scale),
        } for scale in (.6, 1.)} for kind in species}

    candidates = []
    for distance in (280., 420., 550.):
        for direction in range(16):
            angle = direction * math.tau / 16.
            start = geometry.project_placement_point(world, root + u.Vector(
                distance * math.cos(angle), distance * math.sin(angle), 0.))
            if start is None or start.z <= surface + 75.:
                continue
            if geometry.validate_fauna_ground_segment(world, region, "Horse", start, root, 1.):
                candidates.append(start)
    if not candidates:
        raise RuntimeError("No dry horse approach to SouthBrowse passed the saved ground geometry")
    start = candidates[0]
    agent = 41
    if not geometry.set_island_audit_founder_placement(runtime, agent, region, start):
        raise RuntimeError("Could not place the existing horse on the river bank before its first decision")
    low = check(start)
    if land_forage_trial != "Low":
        habitat.set_editor_property("water_surface_z", surface + 70.)
    access = None
    if land_forage_trial == "RootOnlyHigh":
        patches = list(runtime.get_editor_property("fauna_habitat_patches"))
        target, = (p for p in patches if str(p.get_editor_property("id")) == patch_id)
        if not target.get_editor_property("forage_access_points"):
            raise RuntimeError("Root-only control requires a saved alternate access point to remove")
        target.set_editor_property("forage_access_points", [])
        runtime.set_editor_property("fauna_habitat_patches", patches)
    if land_forage_trial == "SavedAccess":
        access, = patch.get_editor_property("forage_access_points")
        if not geometry.validate_fauna_ground_segment(world, region, "Horse", start, access, 1.):
            raise RuntimeError("Saved SouthBrowse access failed the high-water ground approach")
    if land_forage_trial == "BankAccess":
        for distance in (85., 115., 150., 185., 225.):
            for direction in range(16):
                angle = direction * math.tau / 16.
                point = geometry.project_placement_point(world, root + u.Vector(
                    distance * math.cos(angle), distance * math.sin(angle), 0.))
                if (point is not None and point.z > surface + 75.
                        and geometry.validate_fauna_ground_segment(world, region, "Horse", start, point, 1.)
                        and geometry.validate_fauna_ground_segment(world, region, "Horse", point, start, 1.)):
                    access = point
                    break
            if access is not None:
                break
        if access is None:
            raise RuntimeError("No dry point near SouthBrowse passed the high-water ground approach")
        patches = list(runtime.get_editor_property("fauna_habitat_patches"))
        target, = (p for p in patches if str(p.get_editor_property("id")) == patch_id)
        target.set_editor_property("forage_access_points", [access])
        runtime.set_editor_property("fauna_habitat_patches", patches)
        visual, = (a for a in u.GameplayStatics.get_all_actors_of_class(world, u.EcoForagePatchVisual)
                   if str(a.get_editor_property("patch_id")) == patch_id)
        transforms = list(visual.get_editor_property("full_plant_transforms"))
        if len(transforms) < 2:
            raise RuntimeError("SouthBrowse needs existing plants to represent the shared access point")
        plant = transforms[1]
        base = visual.get_editor_property("plants").get_editor_property("static_mesh").get_bounding_box().min.z
        plant.translation = access - visual.get_actor_location() - u.Vector(0., 0., base * plant.scale3d.z)
        transforms[1] = plant
        visual.set_editor_property("full_plant_transforms", transforms)
        visual.rebuild_forage_preview()
    result["lower_river_land_forage"] = {"mode": land_forage_trial, "agent_id": agent, "patch": patch_id,
        "root_cm": list(root.to_tuple()), "start_cm": list(start.to_tuple()), "dry_candidate_count": len(candidates),
        "low_water_routes": low, "active_water_routes": check(start),
        "extra_access_cm": list(access.to_tuple()) if access is not None else None,
        "surface_z_cm": habitat.get_editor_property("water_surface_z")}
    profiles = runtime.get_editor_property("fauna_species")
    result["lower_river_land_forage"]["wade_depth_cm"] = {
        str(profile.get_editor_property("species_id")): profile.get_editor_property("wade_depth")
        for profile in profiles if str(profile.get_editor_property("species_id")) in species
    }


def sample_vegetation(world):
    keys = ("native_step", "habitat_dynamics", "food", "capacity", "mean_moisture", "rain", "grown",
            "environment_lost", "consumed", "ledger_amount", "ledger_capacity", "ledger_consumed",
            "ledger_grown", "ledger_environment_lost", "ledger_habitat_removed", "receipt_sequence")
    vegetation = {}
    for field in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationField):
        grid = json.loads(field.capture_diagnostics())
        if "native_step" in grid:
            vegetation[grid["region"]] = {key: grid[key] for key in keys if key in grid}
    return vegetation


def compare_grassland_forage_link(world, runtime):
    builder = u.EcoCreatureAnimationBuilder
    region = "Grassland"
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    by_id = {str(patch.get_editor_property("id")): patch for patch in patches}
    link_forbs = "-EcoIslandGrasslandForageLink=Forbs" in command.split()
    source_id = "IslandForageWestMeadow" if link_forbs else "IslandForageApproachForbs"
    target_id = "IslandForageApproachForbs" if link_forbs else "IslandForageFloodplainApproach"
    source = by_id[source_id].get_editor_property("center")
    target = by_id[target_id]
    existing = target.get_editor_property("center")
    if target.get_editor_property("forage_access_points"):
        raise RuntimeError("Expected a saved patch with one access point")

    def connected(start, end):
        segments = max(1, math.ceil((end - start).length() / 350.))
        samples = [start, *(builder.project_placement_point(world, start + (end - start) * (i / segments))
                            for i in range(1, segments)), end]
        return all(point is not None for point in samples) and all(
            builder.validate_fauna_ground_segment(world, region, species, a, b, scale)
            for left, right in zip(samples, samples[1:]) for a, b in ((left, right), (right, left))
            for species in ("Horse", "Buffalo") for scale in (.6, 1.))

    delta = existing - source
    separation = delta.length()
    if separation <= 100.:
        raise RuntimeError("Expected separate forage patch centers")
    direction = delta * (1. / separation)
    for distance in (300., 450., 600.):
        point = builder.project_placement_point(world, source + direction * distance)
        if point and (point - existing).length() > 100. and connected(source, point) and connected(point, existing):
            target.set_editor_property("forage_access_points", [point])
            runtime.set_editor_property("fauna_habitat_patches", patches)
            return {"from_patch": source_id, "to_patch": target_id,
                    "from_cm": list(source.to_tuple()), "original_cm": list(existing.to_tuple()),
                    "access_cm": list(point.to_tuple()), "distance_cm": (point - source).length(),
                    "original_distance_cm": separation}
    raise RuntimeError("No nearby bidirectional forage access passed for horses and buffalo")


def compare_meadow_placement(world, runtime):
    builder = u.EcoCreatureAnimationBuilder
    patches = [patch.copy() for patch in runtime.get_editor_property("fauna_habitat_patches")]
    region, patch_id = "Grassland", "IslandForageOpenMeadow"
    index, = (i for i, patch in enumerate(patches) if str(patch.get_editor_property("id")) == patch_id)
    original = u.Vector(*patches[index].get_editor_property("center").to_tuple())
    neighbors = [p.get_editor_property("center") for i, p in enumerate(patches)
                 if i != index and str(p.get_editor_property("region_id")) == region]
    visuals = u.GameplayStatics.get_all_actors_of_class(world, u.EcoForagePatchVisual)
    visual, = (a for a in visuals if str(a.get_editor_property("patch_id")) == patch_id)
    transforms = list(visual.get_editor_property("full_plant_transforms"))

    def spacing(site):
        return min(math.hypot(site.x - p.x, site.y - p.y) for p in neighbors)

    original_spacing = spacing(original)

    def has_connection(site, species, scale):
        previous = original
        for i in range(1, 5):
            point = builder.project_placement_point(world, original + (site - original) * (i / 4.))
            if point is None or not builder.validate_fauna_ground_segment(world, region, species, previous, point, scale):
                return False
            previous = point
        return True

    destination = original
    mode = result["meadow_layout"]
    new_patch_id = f"{patch_id}West"
    if mode in ("Spread", "Split", "Shared"):
        for x, y in ((-1000., 600.), (-500., 1100.), (-1200., 0.), (-800., -650.), (400., -1200.)):
            point = builder.project_placement_point(world, original + u.Vector(x, y, 0.))
            if point is None or spacing(point) < original_spacing + 300.:
                continue
            if all(has_connection(point, species, scale) for species in ("Horse", "Buffalo") for scale in (.6, 1.)):
                destination = point
                break
        if (destination - original).length() < 100.:
            raise RuntimeError("No more widely spaced meadow position with a verified ground connection")
        mesh = visual.get_editor_property("plants").get_editor_property("static_mesh")
        mesh_base = mesh.get_bounding_box().min.z
        moved_plants = transforms[1::2] if mode in ("Split", "Shared") else transforms
        for plant in moved_plants:
            offset = plant.translation
            ground = builder.project_placement_point(world, destination + u.Vector(offset.x, offset.y, 0.))
            if ground is None:
                raise RuntimeError("Moved forage plant lacks a ground surface")
            plant.translation = ground - destination - u.Vector(0., 0., mesh_base * plant.scale3d.z)
        if mode == "Split":
            if not builder.split_island_audit_forage(runtime, patch_id, new_patch_id, destination, transforms[::2], moved_plants):
                raise RuntimeError("Could not split authority stock before the first island step")
            visual, = (a for a in u.GameplayStatics.get_all_actors_of_class(world, u.EcoForagePatchVisual)
                       if str(a.get_editor_property("patch_id")) == new_patch_id)
        elif mode == "Shared":
            patches[index].set_editor_property("forage_access_points", [destination])
            runtime.set_editor_property("fauna_habitat_patches", patches)
            for plant in moved_plants:
                plant.translation += destination - original
            visual.set_editor_property("full_plant_transforms", transforms)
            visual.rebuild_forage_preview()
        else:
            patches[index].set_editor_property("center", destination)
            runtime.set_editor_property("fauna_habitat_patches", patches)
            visual.set_actor_location(destination, False, True)
            visual.set_editor_property("full_plant_transforms", moved_plants)
            visual.rebuild_forage_preview()
    actual_patches = runtime.get_editor_property("fauna_habitat_patches")
    measured_id = new_patch_id if mode == "Split" else patch_id
    patch, = (p for p in actual_patches if str(p.get_editor_property("id")) == measured_id)
    visual_center = patch.get_editor_property("center")
    actual = patch.get_editor_property("forage_access_points")[0] if mode == "Shared" else visual_center
    if (actual - destination).length() > 1. or (visual.get_actor_location() - visual_center).length() > 1.:
        raise RuntimeError(f"Meadow PIE center mismatch: expected {destination}, patch {actual}, visual {visual.get_actor_location()}")
    return {"patch": patch_id, "original": list(original.to_tuple()), "center": list(actual.to_tuple()),
            "spacing_cm": spacing(actual), "original_spacing_cm": original_spacing,
            "split_patch": new_patch_id if mode == "Split" else None}


rain_pattern_region = None


def isolate_region_weather(world, names):
    regions = {str(actor.get_editor_property("region_id")): actor
               for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)}
    for adapter in u.GameplayStatics.get_all_actors_of_class(world, u.EcoRegionEnvironmentAdapter):
        cycle = adapter.get_editor_property("cycle_rainfall")
        authored = adapter.get_editor_property("apply_authored_weather")
        if not (cycle or authored):
            continue
        targets = [str(value) for value in adapter.get_editor_property("region_ids")] or list(regions)
        if not names.intersection(targets):
            continue
        remaining = [name for name in targets if name not in names]
        if remaining:
            adapter.set_editor_property("region_ids", remaining)
        else:
            adapter.set_editor_property("cycle_rainfall", False)
            adapter.set_editor_property("apply_authored_weather", False)
    return {name: regions[name] for name in sorted(names)}


local_soil_weather_regions = {}


def update_local_forage_soil_trial(world, runtime, now):
    if not local_soil_weather_regions:
        if runtime.is_runtime_ready() or not audit_label:
            raise RuntimeError("Local soil trial must configure the saved island before initialization")
        regions = {authored["river"], "ZHighlandRiverTransition"}
        local_soil_weather_regions.update(isolate_region_weather(world, regions))
        patches = list(runtime.get_editor_property("fauna_habitat_patches"))
        tracked = []
        for patch in patches:
            if (patch.get_editor_property("submerged") or str(patch.get_editor_property("region_id")) not in regions
                    or patch.get_editor_property("plant_moisture_need") <= 0.):
                continue
            key = str(patch.get_editor_property("id"))
            patch.set_editor_property("track_local_soil_moisture", True)
            patch.set_editor_property("forage_water_habitat_id", "IslandLowerRiver05"
                                      if local_soil_trial == "Water" and key == "IslandForageSouthBrowse" else "None")
            tracked.append(key)
        runtime.set_editor_property("fauna_habitat_patches", patches)
        habitat, = (actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
                    if str(actor.get_editor_property("habitat_id")) == "IslandLowerRiver05")
        habitat.set_editor_property("water_rain_rise_cm", 24.)
        result["local_forage_soil"] = {"tracked_patches": sorted(tracked), "rain_events": []}
    events = result["local_forage_soil"]["rain_events"]
    rain = .7 if 20. <= now < 80. else 0.
    if not events or events[-1]["rainfall"] != rain:
        for region in local_soil_weather_regions.values():
            state = region.get_environment_state()
            state.set_editor_property("rainfall", rain)
            state.set_editor_property("temperature", 18.)
            state.set_editor_property("weather_state", u.EcoWeatherState.RAIN if rain else u.EcoWeatherState.CLEAR)
            region.set_environment_state(state)
        events.append({"pie_seconds": now, "rainfall": rain})


def stage_seasonal_drift_visual(patch):
    point = patch.get_editor_property("center")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    visual = actors.spawn_actor_from_class(u.EcoForagePatchVisual, point)
    visual.set_editor_property("is_spatially_loaded", False)
    visual.set_editor_property("patch_id", patch.get_editor_property("id"))
    mesh = u.load_asset("/Game/Map_Resource/SkyTown/Meshes/SM_Seaweed02")
    if not mesh:
        raise RuntimeError("Missing the island seaweed asset for the seasonal visual trial")
    base = mesh.get_bounding_box().min.z
    visual.get_editor_property("plants").set_static_mesh(mesh)
    visual.set_editor_property("full_plant_transforms", [
        u.Transform(location=u.Vector(x, y, -base), rotation=u.Rotator(yaw=yaw))
        for x, y, yaw in ((0., 0., 0.), (24., 14., 55.), (-18., -20., -40.))
    ])
    visual.rebuild_forage_preview()


def stage_seasonal_drift_shore(point, source):
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    level = source.get_editor_property("water_surface_z")
    center = u.Vector(point.x + 1680., point.y + 1855., level - 100.)
    reach = actors.spawn_actor_from_class(u.EcoVegetationHabitat, center)
    reach.set_editor_property("is_spatially_loaded", False)
    reach.set_editor_property("habitat_id", DRIFT_SHORE_HABITAT)
    reach.get_editor_property("bounds").set_box_extent(u.Vector(350., 175., 350.), False)
    for name in ("connected_fresh_water", "supports_fauna_swimming", "region_id", "water_surface_z",
                 "fauna_water_current", "fauna_water_temperature_c", "fauna_water_cover_density",
                 "fauna_water_cover_height_cm", "priority", "plant", "drainage", "shade"):
        reach.set_editor_property(name, source.get_editor_property(name))
    reach.set_editor_property("draw_water_surface", False)
    if not reach.is_valid_habitat():
        raise RuntimeError("The Drift shoreline trial requires a valid small water habitat")
    result["drift_shore_trial"] = {"center_cm": list(center.to_tuple()), "extent_cm": [350., 175., 350.]}


def sample_seasonal_drift_visual(world, runtime, completed):
    phases = (("before", 180.), ("exposed", 225.), ("recovered", 249.), ("late", 290.))
    rows = result.setdefault("drift_visual_samples", [])
    if len(rows) >= len(phases):
        return
    phase, sample_time = phases[len(rows)]
    if completed < sample_time - 8.:
        return
    patch, = (p for p in runtime.get_editor_property("fauna_habitat_patches")
              if str(p.get_editor_property("id")) == "IslandRiverDrift")
    point = patch.get_editor_property("center")
    habitat = None
    if drift_surface_trial:
        habitat = seasonal_drift_habitat(u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat))
        surface = habitat.get_editor_property("water_surface_z")
        water_mesh = habitat.get_editor_property("water_surface")
        if not result.get("drift_surface_mesh_ready"):
            u.SystemLibrary.execute_console_command(world, "r.Water.WaterMesh.Enabled 0")
            result["drift_surface_mesh_ready"] = True
        water_mesh.set_world_location(u.Vector(point.x, point.y, surface), False, True)
    if camera is None:
        focus = point + u.Vector(1680., 1855., 0.) if drift_shore_trial else point
        set_camera(world, focus + u.Vector(190., -230., 220.), focus + u.Vector(0., 0., 19.))
    if completed < sample_time:
        return
    patch_id = patch.get_editor_property("id")
    visual, = (a for a in u.GameplayStatics.get_all_actors_of_class(world, u.EcoForagePatchVisual)
               if a.get_editor_property("patch_id") == patch_id)
    plant = visual.get_editor_property("plants")
    authored_plant = visual.get_editor_property("full_plant_transforms")[0]
    transform = plant.get_instance_transform(0, False)
    base = plant.get_editor_property("static_mesh").get_bounding_box().min.z
    stock = runtime.inspect_fauna_habitat_stock(patch_id)
    stock = float(stock[-1] if isinstance(stock, tuple) else stock)
    capacity = patch.get_editor_property("capacity")
    fraction = visual.get_forage_fraction()
    residual = visual.get_editor_property("residual_height_fraction")
    height = transform.scale3d.z / authored_plant.scale3d.z
    root = transform.translation.z + base * transform.scale3d.z
    if (abs(fraction - stock / capacity) > .5 / 255. + .00001
            or abs(height - (residual + (1. - residual) * fraction)) > .0001
            or abs(root) > .001):
        raise RuntimeError(f"Drift visual mismatch: {phase}, stock={stock}, fraction={fraction}, height={height}, root={root}")
    bounds, _ = inspect.inspect_fauna_water(world, authored["river"], point, 1.)
    rows.append({"phase": phase, "authority_seconds": completed, "stock": stock, "capacity": capacity,
                 "visual_fraction": fraction, "height_fraction": height, "root_offset_cm": root,
                 "surface_cm": bounds.y, "point_z_cm": point.z, "submerged": bounds.x < point.z < bounds.y})
    if habitat:
        render_z = water_mesh.get_world_location().z
        if abs(render_z - bounds.y) > .01 or not water_mesh.is_visible():
            raise RuntimeError(f"Expected the Drift test surface to match the selected fauna water level: {phase}")
        rows[-1]["surface_profile"] = sample_drift_surface_profile(world, point, render_z)
    capture(world, f"Drift_{phase}")


def sample_drift_surface_profile(world, point, render_z):
    rows = []
    for x in range(-1960, 1961, 140):
        for y in range(-1960, 1961, 140):
            location = point + u.Vector(x, y, 0.)
            bed = mink_landscape_z(world, location)
            water = inspect.inspect_fauna_water(world, authored["river"], location, 1.)
            rows.append({"offset_cm": [x, y], "bed_cm": bed, "render_depth_cm": render_z - bed
                         if bed is not None else None, "swimmable_at_1cm": bool(water),
                         "fauna_surface_cm": water[0].y if water else None})
    return rows


def seasonal_drift_habitat(actors):
    habitat, = (actor for actor in actors if isinstance(actor, u.EcoVegetationHabitat)
                and str(actor.get_editor_property("habitat_id")) == "IslandLowerRiver05")
    return habitat


def update_seasonal_drift_water(world, runtime, completed):
    if completed < 205.:
        return
    changes = result.setdefault("drift_seasonal_water", [])
    if len(changes) == 2 or (changes and completed < 245.):
        return
    river = authored["river"]
    patch, = (p for p in runtime.get_editor_property("fauna_habitat_patches")
              if str(p.get_editor_property("id")) == "IslandRiverDrift")
    point = patch.get_editor_property("center")
    actors = u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
    habitat = seasonal_drift_habitat(actors)
    if habitat.get_editor_property("water_rain_rise_cm") or habitat.get_editor_property("water_level_rise"):
        raise RuntimeError("Seasonal Drift trial requires the saved static water provider")
    old = habitat.get_editor_property("water_surface_z")
    surface = changes[0]["previous_surface_cm"] if changes else point.z - 6.
    habitat.set_editor_property("water_surface_z", surface)
    if drift_shore_trial:
        shore, = (actor for actor in actors if str(actor.get_editor_property("habitat_id")) == DRIFT_SHORE_HABITAT)
        shore.set_editor_property("water_surface_z", surface)
    bounds, _ = inspect.inspect_fauna_water(world, river, point, 1.)
    if (bounds.x < point.z < bounds.y) != bool(changes):
        raise RuntimeError("Expected exposure on drawdown and submergence on restoration")
    changes.append({"authority_seconds": completed, "previous_surface_cm": old,
                    "surface_cm": bounds.y, "point_z_cm": point.z})


def update_drift_rain_pulse(world, completed):
    changes = result.setdefault("drift_rain_pulse", [])
    rain = .85 if 205. <= completed < 245. else .35
    if changes and changes[-1]["rainfall"] == rain:
        return
    river_id = authored["river"]
    region = isolate_region_weather(world, {river_id})[river_id] if not changes else next(
        actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)
        if str(actor.get_editor_property("region_id")) == river_id)
    state = region.get_environment_state()
    state.set_editor_property("rainfall", rain)
    region.set_environment_state(state)
    changes.append({"completed_authority_seconds": completed, "rainfall": rain})


def update_rain_pattern(world, now):
    global rain_pattern_region
    if "rain_pattern_events" not in result:
        runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
        if not runtime or not runtime.is_runtime_ready():
            return
        if result.get("regional_rain"):
            rain_pattern_region = isolate_region_weather(world, {"Grassland"})["Grassland"]
            u.SystemLibrary.execute_console_command(world, "eco.Grass.Auto Grassland")
        result["rain_pattern_events"] = []
    events = result["rain_pattern_events"]
    elapsed = now - events[0]["time"] if events else 0.
    second = math.floor(elapsed + 0.00001)
    if result["rain_pattern"] == "Block":
        wet = 20 <= second < 80
    else:
        wet = any(start <= second < start + 20 for start in (20, 50, 80))
    rain = .7 if wet else 0.
    if not events or events[-1]["rain"] != rain:
        if rain_pattern_region is None:
            u.SystemLibrary.execute_console_command(world, f"eco.Grass.Climate Grassland {rain} 18")
        else:
            state = rain_pattern_region.get_environment_state()
            state.set_editor_property("rainfall", rain)
            state.set_editor_property("temperature", 18.)
            state.set_editor_property("weather_state", u.EcoWeatherState.RAIN if wet else u.EcoWeatherState.CLEAR)
            rain_pattern_region.set_environment_state(state)
        events.append({"time": now, "rain": rain})


def transition_geometry():
    first = u.Vector(46680., 45480., 3098.59)
    last = u.Vector(40520., 38820., 3098.59)
    return {"region_id": "ZHighlandRiverTransition", "center_cm": list(((first + last) * .5).to_tuple()),
            "transect_cm": [list((first + (last - first) * (index / 20.)).to_tuple()) for index in range(21)]}


GRASSLAND_TRANSIT_REGION = "ZGrasslandRiverTransit"


def author_grassland_passage():
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    existing = actors.get_all_level_actors()
    runtime, = (actor for actor in existing if isinstance(actor, u.EcoCreatureIntegrationSpawner))
    regions = {str(actor.get_editor_property("region_id")): actor for actor in existing
               if isinstance(actor, u.EcologyRegion)}
    if GRASSLAND_TRANSIT_REGION in regions:
        raise RuntimeError("Grassland trial requires the unmodified Grassland–LowerRiver gap")
    grassland, lower_river = regions["Grassland"], regions["LowerRiver"]
    # Central dry transect from the region-seam survey, with additional approach inside Grassland.
    first = u.Vector(90000., 55980., -4283.84)
    last = u.Vector(89889.48, 46391.60, -4194.39)
    center = (first + last) * .5
    rotation = u.MathLibrary.find_look_at_rotation(first, last)
    corridor = actors.spawn_actor_from_class(u.EcologyRegion, center, rotation)
    corridor.set_actor_label("JYU Grassland–LowerRiver Transit")
    for key, value in dict(region_id=GRASSLAND_TRANSIT_REGION, adjacent_region_ids=["Grassland", "LowerRiver"],
                           initial_food_amount=0., food_capacity=0., food_regeneration_rate=0.,
                           is_spatially_loaded=False, environment_state=grassland.get_environment_state()).items():
        corridor.set_editor_property(key, value)
    corridor.get_editor_property("region_bounds").set_box_extent(u.Vector((last - first).length() * .5 + 350., 450., 500.))
    group = u.EcoCreatureSpawnGroup()
    for key, value in dict(region_id=GRASSLAND_TRANSIT_REGION, herbivores=0, wolves=0,
                           rules_only=True, fauna_transit=True).items():
        group.set_editor_property(key, value)
    schedule = group.get_editor_property("schedule")
    schedule.set_editor_property("day_count", 0)
    schedule.set_editor_property("night_count", 0)
    group.set_editor_property("schedule", schedule)
    runtime.modify()
    runtime.set_editor_property("groups", [*runtime.get_editor_property("groups"), group])
    points = [first + (last - first) * (i / 32.) for i in range(33)]
    approach = [u.Vector(90000., y, -4283.84) for y in range(60200, 55980, -350)]
    # Keep both seam brackets and use fewer stopping points on the straight, surveyed section.
    inbound, outbound = points[:32], points[1:][::-1]
    if result.get("grassland_sparse_approach"):
        approach = approach[::3]
        inbound = [*points[:1], *points[1:30:4], points[31]]
        outbound = [points[-1], *points[30:2:-4], points[1]]
    for source, path in ((grassland, [*approach, *inbound]),
                         (lower_river, [u.Vector(last.x, 45800., last.z), *outbound])):
        if result["save_grassland_passage"]:
            path = [u.EcoCreatureAnimationBuilder.project_placement_point(editor.get_editor_world(), point)
                    for point in path]
            if any(point is None for point in path):
                raise RuntimeError("Verified route cannot be projected in the editor world")
        source_name = str(source.get_editor_property("region_id"))
        source.modify()
        source.set_editor_property("adjacent_region_ids",
                                   [*source.get_editor_property("adjacent_region_ids"), u.Name(GRASSLAND_TRANSIT_REGION)])
        route = actors.spawn_actor_from_class(u.EcoHerdMigrationRoute, path[0])
        route.set_actor_label(f"JYU Grassland Transit Route – {source_name}")
        for key, value in dict(from_region=source_name, to_region=GRASSLAND_TRANSIT_REGION, points=path,
                               allow_rule_fauna_passage=True, bidirectional=True, is_spatially_loaded=False).items():
            route.set_editor_property(key, value)
        if not route.is_valid_route():
            raise RuntimeError(f"Invalid {source_name} trial route")
    if result.get("grassland_near_forage"):
        patch_id = "IslandForageNorthForbs"
        patches = list(runtime.get_editor_property("fauna_habitat_patches"))
        patch, = (patch for patch in patches if str(patch.get_editor_property("id")) == patch_id)
        if patch.get_editor_property("forage_access_points"):
            raise RuntimeError("Trial expects the original NorthForbs layout")
        point = last + u.Vector(0., -440., 0.)
        result["grassland_forage_move"] = {"patch": patch_id, "original_cm": list(patch.get_editor_property("center").to_tuple()),
                                          "trial_cm": list(point.to_tuple())}
        move_grassland_forage(existing, runtime, patch_id, point, result["save_grassland_passage"])


def move_grassland_forage(actors, runtime, patch_id, point, project):
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    patch, = (item for item in patches if str(item.get_editor_property("id")) == patch_id)
    visual, = (actor for actor in actors if isinstance(actor, u.EcoForagePatchVisual)
               and str(actor.get_editor_property("patch_id")) == patch_id)
    if project:
        world = editor.get_editor_world()
        point = u.EcoCreatureAnimationBuilder.project_placement_point(world, point)
        if point is None:
            raise RuntimeError("Forage position cannot be projected in the editor world")
        mesh_base = visual.get_editor_property("plants").get_editor_property("static_mesh").get_bounding_box().min.z
        transforms = list(visual.get_editor_property("full_plant_transforms"))
        for transform in transforms:
            offset = transform.translation
            ground = u.EcoCreatureAnimationBuilder.project_placement_point(world, point + u.Vector(offset.x, offset.y, 0.))
            if ground is None:
                raise RuntimeError("Relocated forage visual has no supporting ground")
            transform.translation = ground - point - u.Vector(0., 0., mesh_base * transform.scale3d.z)
    patch.set_editor_property("center", point)
    runtime.modify()
    runtime.set_editor_property("fauna_habitat_patches", patches)
    visual.modify()
    if project:
        visual.set_editor_property("full_plant_transforms", transforms)
    visual.set_actor_location(point, False, True)
    visual.rebuild_forage_preview()
    return point


def stage_grassland_forage_network():
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    runtime, = (actor for actor in actors if isinstance(actor, u.EcoCreatureIntegrationSpawner))
    routes = [actor for actor in actors if isinstance(actor, u.EcoHerdMigrationRoute)
              and str(actor.get_editor_property("to_region")) == GRASSLAND_TRANSIT_REGION]
    if len(routes) != 2 or any(route.get_editor_property("enabled") for route in routes):
        raise RuntimeError("Expected both held Grassland routes")
    destination = next(route for route in routes if str(route.get_editor_property("from_region")) == "LowerRiver")
    exit_point = destination.get_editor_property("points")[1]
    placements = {"IslandForageNorthForbs": exit_point + u.Vector(0., -440., 0.),
                  "IslandForageNorthSedges": exit_point + u.Vector(-750., -1030., 0.)}
    if result["grassland_forage_stop"]:
        region, = (actor for actor in actors if isinstance(actor, u.EcologyRegion)
                   and str(actor.get_editor_property("region_id")) == GRASSLAND_TRANSIT_REGION)
        groups = list(runtime.get_editor_property("groups"))
        group, = (item for item in groups if str(item.get_editor_property("region_id")) == GRASSLAND_TRANSIT_REGION)
        group.set_editor_property("fauna_transit", False)
        runtime.set_editor_property("groups", groups)
        placements["IslandForageNorthSedges"] = region.get_actor_location()
        if result["grassland_forage_near_entry"]:
            placements["IslandForageNorthSedges"] = u.Vector(89989.65, 55081.09, -4283.84)
    result["grassland_forage_sites_cm"] = {
        patch_id: list(move_grassland_forage(actors, runtime, patch_id, point, False).to_tuple())
        for patch_id, point in placements.items()
    }
    if "-EcoIslandGrasslandSharedSedges" in command.split():
        patches = list(runtime.get_editor_property("fauna_habitat_patches"))
        sedges, = (item for item in patches if str(item.get_editor_property("id")) == "IslandForageNorthSedges")
        sedges.set_editor_property("forage_access_points", [exit_point + u.Vector(-230., -280., 0.)])
        runtime.set_editor_property("fauna_habitat_patches", patches)
        result["grassland_shared_sedges"] = True
    if result["grassland_forage_stop"]:
        patches = list(runtime.get_editor_property("fauna_habitat_patches"))
        patch, = (item for item in patches if str(item.get_editor_property("id")) == "IslandForageNorthSedges")
        patch.set_editor_property("region_id", GRASSLAND_TRANSIT_REGION)
        runtime.set_editor_property("fauna_habitat_patches", patches)
    short_approach = re.search(r"(?:^|\s)-EcoIslandGrasslandShortApproach=(Moderate|Deep)(?:\s|$)", command)
    if short_approach:
        grassland = next(route for route in routes if str(route.get_editor_property("from_region")) == "Grassland")
        points = list(grassland.get_editor_property("points"))
        limit_y = 59200. if short_approach[1] == "Moderate" else 58000.
        shortened = [point for point in points if point.y <= limit_y]
        if len(shortened) < 2 or len(shortened) == len(points):
            raise RuntimeError("Could not trim the Grassland approach while retaining the seam")
        grassland.set_editor_property("points", shortened)
        if not grassland.is_valid_route():
            raise RuntimeError("Shortened Grassland route is invalid")
        result["grassland_short_approach"] = {
            "layout": short_approach[1],
            "original_start_cm": list(points[0].to_tuple()),
            "trial_start_cm": list(shortened[0].to_tuple()),
        }
    for route in routes:
        route.set_editor_property("enabled", True)


def inspect_grassland_passage(world, runtime):
    builder = u.EcoCreatureAnimationBuilder
    regions = sorted((str(actor.get_editor_property("region_id")), actor.get_editor_property("region_bounds"))
                     for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion))
    routes = [route for route in u.GameplayStatics.get_all_actors_of_class(world, u.EcoHerdMigrationRoute)
              if str(route.get_editor_property("to_region")) == GRASSLAND_TRANSIT_REGION]
    projected = {}
    for route in routes:
        name = str(route.get_editor_property("from_region"))
        original = list(route.get_editor_property("points"))
        points = [builder.project_placement_point(world, point) for point in original]
        if any(point is None for point in points):
            raise RuntimeError(f"Missing ground on {name} trial route")
        if result["grassland_passage_saved"]:
            if any((before - after).length() > 1. for before, after in zip(original, points)):
                raise RuntimeError(f"Saved {name} route differs from the ground surface")
            points = original
        else:
            route.set_editor_property("points", points)
        projected[name] = points
    grassland = projected["Grassland"]
    river = projected["LowerRiver"]
    path = [*grassland, *river[:2][::-1]]
    measured_path = [path[0]]
    for a, b in zip(path, path[1:]):
        span = max(1, math.ceil((b - a).length() / 350.))
        measured_path.extend(builder.project_placement_point(world, a + (b - a) * (i / span)) for i in range(1, span + 1))
    if any(point is None for point in measured_path):
        raise RuntimeError("Missing ground between Grassland passage waypoints")
    owners = []
    for point in measured_path:
        for name, bounds in regions:
            local = u.MathLibrary.inverse_transform_location(bounds.get_world_transform(), point)
            if all(abs(value) <= limit for value, limit in zip(local.to_tuple(), bounds.get_unscaled_box_extent().to_tuple())):
                owners.append(name)
                break
        else:
            raise RuntimeError(f"No regional owner at {point}")
    if list(dict.fromkeys(owners)) != ["Grassland", GRASSLAND_TRANSIT_REGION, "LowerRiver"]:
        raise RuntimeError(f"Unexpected trial ownership: {owners}")
    species_ids = ("Horse", "Buffalo", "Pig", "Crow")
    checks = {species: {str(scale): [
        builder.validate_fauna_ground_segment(world, "None", species, a, b, scale)
        and builder.validate_fauna_ground_segment(world, "None", species, b, a, scale)
        for a, b in zip(measured_path, measured_path[1:])] for scale in (.6, 1.)}
        for species in species_ids}
    exit_point = measured_path[owners.index("LowerRiver")]
    profiles = {str(row.get_editor_property("species_id")): row for row in runtime.get_editor_property("fauna_species")}

    def ground_access(origin, point, region, species):
        distance = (point - origin).length()
        if distance > 1500.:
            return None
        # The native helper accepts segments of at most 600 cm.
        count = max(1, math.ceil(distance / 350.))
        samples = [origin, *(builder.project_placement_point(world, origin + (point - origin) * (i / count))
                             for i in range(1, count)), point]
        return not any(sample is None for sample in samples) and all(
            builder.validate_fauna_ground_segment(world, region, species, a, b, scale)
            for a, b in zip(samples, samples[1:]) for scale in (.6, 1.))

    food = {}
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        if (str(patch.get_editor_property("region_id")) not in ("LowerRiver", GRASSLAND_TRANSIT_REGION)
                or patch.get_editor_property("submerged")):
            continue
        patch_id = str(patch.get_editor_property("id"))
        consumers = set(map(str, patch.get_editor_property("consumers")))
        points = [patch.get_editor_property("center"), *patch.get_editor_property("forage_access_points")]
        origin = exit_point if str(patch.get_editor_property("region_id")) == "LowerRiver" else measured_path[
            owners.index(GRASSLAND_TRANSIT_REGION)]
        food[patch_id] = {
            species: [{
                "point_cm": list(point.to_tuple()), "distance_cm": (point - origin).length(),
                "within_food_sight_range": (point - origin).length() <= 1.5 * profiles[species].get_editor_property("sight_range"),
                "center_line_clear": builder.has_fauna_audit_sight(
                    world, origin + u.Vector(0., 0., profiles[species].get_editor_property("eye_height")),
                    point + u.Vector(0., 0., 5.)),
                "ground_path_clear": ground_access(origin, point, str(patch.get_editor_property("region_id")), species),
            } for point in points] for species in species_ids if species in consumers
        }
        if patch_id in result.get("grassland_forage_sites_cm", {}):
            visual, = (actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoForagePatchVisual)
                       if str(actor.get_editor_property("patch_id")) == patch_id)
            visual.set_actor_location(points[0], False, True)
            result["grassland_forage_sites_cm"][patch_id] = list(points[0].to_tuple())
    if result.get("grassland_shared_sedges"):
        access = food["IslandForageNorthSedges"]["Horse"][1]
        if not all(access[key] for key in ("within_food_sight_range", "center_line_clear", "ground_path_clear")):
            raise RuntimeError("The trial sedge access is not connected to the river exit for horses")
    center = next(actor.get_actor_location() for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)
                  if str(actor.get_editor_property("region_id")) == GRASSLAND_TRANSIT_REGION)
    return {"center_cm": list(center.to_tuple()), "points_cm": [list(point.to_tuple()) for point in measured_path],
            "surveyed_path_length_cm": sum(math.hypot(b.x - a.x, b.y - a.y)
                                           for a, b in zip(measured_path, measured_path[1:])),
            "species_nominal_walk_cm_per_second": {species: profiles[species].get_editor_property("walk_speed")
                                                    for species in species_ids},
            "route_waypoints": {region: len(points) for region, points in projected.items()},
            "routes_enabled": {str(route.get_editor_property("from_region")): bool(route.get_editor_property("enabled"))
                               for route in routes},
            "owners": owners, "ground_checks": checks, "destination_food_sites": food}


def extend_highland_approach(world, points):
    builder = u.EcoCreatureAnimationBuilder
    goal = u.Vector(48950., 49000., 3137.18)
    original = points[0]
    added = []
    while len(added) < 8 and math.hypot(goal.x - points[0].x, goal.y - points[0].y) > 350.:
        start = builder.project_placement_point(world, points[0])
        if start is None:
            break
        heading = math.atan2(goal.y - start.y, goal.x - start.x)
        for offset in (0, 30, -30, 60, -60, 85, -85):
            angle = heading + math.radians(offset)
            end = builder.project_placement_point(world, start + u.Vector(math.cos(angle), math.sin(angle), 0.) * 350.)
            if end is None or any((end - point).length() < 250. for point in [original, *added]):
                continue
            if not all(builder.validate_fauna_ground_segment(world, "Highland", species, a, b, scale)
                       for species in ("Bighorn", "GoldenEagle") for scale in (.6, 1.)
                       for a, b in ((start, end), (end, start))):
                continue
            points.insert(0, end)
            added.append(end)
            break
        else:
            break
    if not added:
        raise RuntimeError(f"Could not extend Highland ground approach from {original}")
    result["highland_approach_points"] = [list(p.to_tuple()) for p in added]
    return points


def author_transition_region():
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    runtime, = (actor for actor in actors.get_all_level_actors() if isinstance(actor, u.EcoCreatureIntegrationSpawner))
    regions = {str(actor.get_editor_property("region_id")): actor for actor in actors.get_all_level_actors()
               if isinstance(actor, u.EcologyRegion)}
    geometry = transition_geometry()
    corridor_id = geometry["region_id"]
    if corridor_id in regions:
        raise RuntimeError("Expected the unmodified island region layout")
    highland, riverbank = regions["Highland"], regions["Riverbank"]
    waypoints = [u.Vector(*point) for point in geometry["transect_cm"]]
    first, last = waypoints[0], waypoints[-1]
    length = (last - first).length()
    direction = (last - first) * (1. / length)
    center = (first + last) * .5
    rotation = u.MathLibrary.find_look_at_rotation(first, last)
    corridor = actors.spawn_actor_from_class(u.EcologyRegion, center, rotation)
    corridor.set_actor_label("JYU Highland–Riverbank Transition")
    for key, value in dict(region_id=corridor_id, adjacent_region_ids=["Highland", "Riverbank"],
                           initial_food_amount=0., food_capacity=0., food_regeneration_rate=0.,
                           is_spatially_loaded=False,
                           environment_state=(riverbank if result.get("transition_habitat_author") else highland).get_environment_state()).items():
        corridor.set_editor_property(key, value)
    corridor.get_editor_property("region_bounds").set_box_extent(u.Vector(length * .5 + 350., 450., 500.))
    group = u.EcoCreatureSpawnGroup()
    for key, value in dict(region_id=corridor_id, herbivores=0, wolves=0, rules_only=True,
                           fauna_transit=not result["transition_control"]).items():
        group.set_editor_property(key, value)
    schedule = group.get_editor_property("schedule")
    schedule.set_editor_property("day_count", 0)
    schedule.set_editor_property("night_count", 0)
    group.set_editor_property("schedule", schedule)
    runtime.set_editor_property("groups", [*runtime.get_editor_property("groups"), group])
    highland_approach = [first - direction * 2200., first - direction * 900.]
    river_approach = [last + direction * 2200., last + direction * 900.]
    if result.get("transition_extended_approach"):
        highland_approach[:0] = [u.Vector(47000., 49600., 3137.18), u.Vector(47150., 48400., 3137.18)]
    if result.get("transition_habitat_river_approach"):
        river_approach[:0] = [u.Vector(36550., 35250., last.z), u.Vector(37800., 36300., last.z)]
    for source, target, points in (
            (highland, corridor, [*highland_approach, *waypoints[:20]]),
            (riverbank, corridor, [*river_approach, *waypoints[1:][::-1]])):
        adjacent = list(source.get_editor_property("adjacent_region_ids"))
        source.set_editor_property("adjacent_region_ids", [*adjacent, u.Name(corridor_id)])
        route = actors.spawn_actor_from_class(u.EcoHerdMigrationRoute, points[0])
        route.set_actor_label(f"JYU Transit Route – {source.get_editor_property('region_id')}")
        for key, value in dict(from_region=source.get_editor_property("region_id"),
                               to_region=target.get_editor_property("region_id"), points=points,
                               allow_rule_fauna_passage=True, bidirectional=True,
                               is_spatially_loaded=False).items():
            route.set_editor_property(key, value)
        if not route.is_valid_route():
            raise RuntimeError("Invalid transition route")
    if result.get("transition_founder_trial"):
        patches = list(runtime.get_editor_property("fauna_habitat_patches"))
        patch, = (p for p in patches if str(p.get_editor_property("id")) == "IslandForageWestForbs")
        target = last + direction * 600.
        patch.set_editor_property("center", target)
        runtime.set_editor_property("fauna_habitat_patches", patches)
        result["transition_destination_patch"] = {"id": "IslandForageWestForbs", "center_cm": list(target.to_tuple())}
    if result.get("transition_habitat"):
        patches = list(runtime.get_editor_property("fauna_habitat_patches"))
        source, = (p for p in patches if str(p.get_editor_property("id")) == "IslandForageWestForbs")
        site = source.copy()
        site.set_editor_property("id", "IslandTransitionForbs")
        site.set_editor_property("region_id", corridor_id)
        distance = 470. if result.get("transition_habitat_near") else 720.
        site.set_editor_property("center", last - direction * distance)
        for field in ("capacity", "regrowth_per_second", "plant_dry_loss_per_second"):
            value = source.get_editor_property(field)
            source.set_editor_property(field, value * .5)
            site.set_editor_property(field, value * .5)
        runtime.set_editor_property("fauna_habitat_patches", [*patches, site])
        result["transition_habitat_position_cm"] = list(site.get_editor_property("center").to_tuple())
        if result.get("transition_habitat_author"):
            author_saved_transition_habitat(actors, corridor_id, site.get_editor_property("center"))
    if result.get("transition_wall"):
        wall = actors.spawn_actor_from_class(u.StaticMeshActor, last + u.Vector(0., 0., 140.), rotation)
        wall.set_actor_label("PIE Transit Collision Wall")
        wall.set_editor_property("is_spatially_loaded", False)
        mesh = wall.static_mesh_component
        mesh.set_static_mesh(u.load_asset("/Engine/BasicShapes/Cube"))
        mesh.set_collision_profile_name("BlockAll")
        mesh.set_mobility(u.ComponentMobility.MOVABLE)
        wall.set_actor_scale3d(u.Vector(.8, 11., 3.))
        wall.set_actor_enable_collision(False)
        wall.tags = [u.Name("JYU.TransitCollisionWall")]
    result["transition_authoring"] = geometry


def author_saved_transition_habitat(actors, region_id, center):
    existing = actors.get_all_level_actors()
    adapters = [a for a in existing if isinstance(a, u.EcoRegionEnvironmentAdapter)
                and (a.get_editor_property("cycle_rainfall") or a.get_editor_property("apply_authored_weather"))]
    adapter, = (a for a in adapters if a.get_actor_label() == "JYU_Island_Riverbank_Rain")
    ids = list(adapter.get_editor_property("region_ids"))
    if list(map(str, ids)) != ["Riverbank"] or any(
            not a.get_editor_property("region_ids") or region_id in map(str, a.get_editor_property("region_ids"))
            for a in adapters):
        raise RuntimeError("Expected a single existing rain writer for the authored transition habitat")
    adapter.set_editor_property("region_ids", [*ids, u.Name(region_id)])

    source, = (a for a in existing if isinstance(a, u.EcoForagePatchVisual)
               and str(a.get_editor_property("patch_id")) == "IslandForageWestForbs")
    visual = actors.spawn_actor_from_class(source.get_class(), center)
    visual.set_actor_label("JYU Transition Forbs")
    visual.set_editor_property("is_spatially_loaded", False)
    visual.set_editor_property("patch_id", "IslandTransitionForbs")
    for name in ("residual_height_fraction", "keep_woody_stems"):
        visual.set_editor_property(name, source.get_editor_property(name))
    for name in ("plants", "woody_stems"):
        component = visual.get_editor_property(name)
        donor = source.get_editor_property(name)
        component.set_static_mesh(donor.get_editor_property("static_mesh"))
        component.set_cull_distances(3300, 5200)
        component.set_cast_shadow(donor.get_editor_property("cast_shadow"))
        for index in range(donor.get_num_materials()):
            component.set_material(index, donor.get_material(index))
    source_transforms = list(source.get_editor_property("full_plant_transforms"))
    if len(source_transforms) < 2:
        raise RuntimeError("Expected the existing Riverbank forage cluster transforms")
    split = (len(source_transforms) + 1) // 2
    source.set_editor_property("full_plant_transforms", source_transforms[:split])
    visual.set_editor_property("full_plant_transforms", source_transforms[split:])
    source.rebuild_forage_preview()
    visual.rebuild_forage_preview()


def inspect_transition_region(world, runtime):
    region_id = result["transition_authoring"]["region_id"]
    group, = (g for g in runtime.get_editor_property("groups") if str(g.get_editor_property("region_id")) == region_id)
    if (not group.get_editor_property("rules_only")
            or group.get_editor_property("fauna_transit") == result["transition_control"]
            or any(group.get_editor_property(name) for name in ("herbivores", "wolves", "fauna"))):
        raise RuntimeError("Transition region unexpectedly created a Native stage or a starting roster")
    corridor_patches = {str(p.get_editor_property("id")) for p in runtime.get_editor_property("fauna_habitat_patches")
                        if str(p.get_editor_property("region_id")) == region_id}
    expected_patches = {"IslandTransitionForbs"} if result.get("transition_habitat") else set()
    if corridor_patches != expected_patches:
        raise RuntimeError(f"Unexpected authored food in transition region: {corridor_patches}")
    regions = {str(actor.get_editor_property("region_id")): actor for actor in u.GameplayStatics.get_all_actors_of_class(
        world, u.EcologyRegion)}
    corridor = regions[region_id]
    if any(corridor.get_editor_property(name) for name in ("initial_food_amount", "food_capacity", "food_regeneration_rate")):
        raise RuntimeError("Transition region changed the regional food budget")
    transforms = []
    for name, actor in sorted(regions.items()):
        bounds = actor.get_editor_property("region_bounds")
        transforms.append((name, bounds.get_world_transform(), bounds.get_unscaled_box_extent()))
    builder = u.EcoCreatureAnimationBuilder
    routes = [route for route in u.GameplayStatics.get_all_actors_of_class(world, u.EcoHerdMigrationRoute)
              if str(route.get_editor_property("to_region")) == region_id
              and route.get_editor_property("allow_rule_fauna_passage") and route.is_valid_route()]
    if len(routes) != 2:
        raise RuntimeError("Both transition routes must be available in PIE")

    def owners_at(point):
        owners = []
        for name, transform, extent in transforms:
            local = u.MathLibrary.inverse_transform_location(transform, point)
            if all(abs(value) <= limit for value, limit in zip(local.to_tuple(), extent.to_tuple())):
                owners.append(name)
        return owners

    transect = []
    for coordinates in result["transition_authoring"]["transect_cm"]:
        point = builder.project_placement_point(world, u.Vector(*coordinates))
        owners = owners_at(point) if point is not None else []
        if not owners:
            raise RuntimeError("Transition ground has no regional owner")
        transect.append({"point_cm": list(point.to_tuple()), "owner": owners[0], "all_owners": owners})
    ordered = list(dict.fromkeys(row["owner"] for row in transect))
    if ordered != ["Highland", region_id, "Riverbank"]:
        raise RuntimeError(f"Unexpected authority ordering on the transition: {ordered}")
    seams = {}
    for route in routes:
        source = str(route.get_editor_property("from_region"))
        points = list(route.get_editor_property("points"))
        if source == "Highland" and result.get("highland_approach_trial"):
            checks = {}
            for species in ("Bighorn", "GoldenEagle"):
                for scale in (.6, 1.):
                    ground = [builder.project_placement_point(world, points[0] + (points[1] - points[0]) * (i / 8.))
                              for i in range(9)]
                    checks[f"{species}:{scale}"] = all(point is not None for point in ground) and all(
                        builder.validate_fauna_ground_segment(world, source, species, a, b, scale)
                        and builder.validate_fauna_ground_segment(world, source, species, b, a, scale)
                        for a, b in zip(ground, ground[1:]))
            result["highland_approach_trial_checks"] = checks
            if not all(checks.values()):
                raise RuntimeError(f"Added Highland approach failed ground validation: {checks}")
        extended = (source == "Highland" and result.get("transition_extended_approach")) or (
            source == "Riverbank" and result.get("transition_habitat_river_approach"))
        if extended:
            species = "Bighorn" if source == "Highland" else "Jackrabbit"
            approach = points[:4]
            body_checks = []
            for a, b in zip(approach, approach[1:]):
                span = math.ceil((b - a).length() / 250.)
                ground = [builder.project_placement_point(world, a + (b - a) * (index / span))
                          for index in range(span + 1)]
                body_checks.append(all(ground) and all(
                    builder.validate_fauna_ground_segment(world, source, species, first, last, 1.)
                    and builder.validate_fauna_ground_segment(world, source, species, last, first, 1.)
                    for first, last in zip(ground, ground[1:])))
            result[f"transition_{source.lower()}_approach_checks"] = body_checks
        transitions = [(start, end) for start, end in zip(points, points[1:])
                       if owners_at(start)[:1] == [source] and owners_at(end)[:1] == [region_id]]
        (start, end), = transitions
        mid = (start + end) * .5
        for _ in range(20):
            mid = (start + end) * .5
            if owners_at(mid)[:1] == [source]:
                start = mid
            else:
                end = mid
        direction = points[-1] - points[0]
        direction = direction * (1. / direction.length())
        start, end = (builder.project_placement_point(world, mid + direction * offset) for offset in (-10., 10.))
        if start is None or end is None or owners_at(start)[:1] != [source] or owners_at(end)[:1] != [region_id]:
            raise RuntimeError(f"Missing short physical seam for {source}")
        species = ("Rat", "Bighorn", "Horse", "Buffalo", "Fox", "Mink")
        passes = {kind: all(builder.validate_fauna_ground_segment(world, "None", kind, a, b, 1.)
                            for a, b in ((start, end), (end, start))) for kind in species}
        seams[source] = {"span_cm": (end - start).length(), "round_trip_ground": passes,
                         "endpoints_cm": [list(p.to_tuple()) for p in (start, end)]}
    return {"owners": ordered, "transect": transect, "seams": seams}


def place_transition_founder(world, runtime):
    points = result["transition_authoring"]["transect_cm"]
    first, last = u.Vector(*points[0]), u.Vector(*points[-1])
    position = first + (first - last) * .17
    rows = [read_agent(world, agent) for agent in inspect.get_authority_agent_ids(world)]
    bighorn = min(int(row["stable_id"]) for row in rows if row and row["species"] == "Bighorn" and row["region"] == "Highland")
    if not u.EcoCreatureAnimationBuilder.set_island_audit_founder_placement(runtime, bighorn, "Highland", position):
        raise RuntimeError("Could not place the existing bighorn near the corridor")
    result["transition_founder"] = {"id": bighorn, "position_cm": list(position.to_tuple())}


def place_transition_rabbit(world, runtime):
    points = result["transition_authoring"]["transect_cm"]
    first, last = u.Vector(*points[0]), u.Vector(*points[-1])
    position = last + (last - first) * .035
    rows = [read_agent(world, agent) for agent in inspect.get_authority_agent_ids(world)]
    rabbit = min(int(row["stable_id"]) for row in rows if row and row["species"] == "Jackrabbit" and row["region"] == "Riverbank")
    if not u.EcoCreatureAnimationBuilder.set_island_audit_founder_placement(runtime, rabbit, "Riverbank", position):
        raise RuntimeError("Could not place the existing jackrabbit near the corridor")
    result["transition_rabbit"] = rabbit


def apply_transition_habitat_weather(world):
    region, = (a for a in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)
               if str(a.get_editor_property("region_id")) == result["transition_authoring"]["region_id"])
    climate = region.get_environment_state()
    for key, value in (("rainfall", .65), ("humidity", .69), ("temperature", 18.)):
        climate.set_editor_property(key, value)
    region.set_environment_state(climate)
    result["transition_habitat_climate"] = {"rainfall": .65, "humidity": .69, "temperature_c": 18.}


def sample_transition_river_weather(world, now):
    # The PIE comparison samples the live adjacent region. Run before the next
    # resource step without modifying the source or its existing weather actors.
    region_id = result["transition_authoring"]["region_id"]
    actors = {str(a.get_editor_property("region_id")): a
              for a in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)}
    source = actors["Riverbank"].get_environment_state()
    target = actors[region_id].get_environment_state()
    fields = ("rainfall", "humidity", "temperature", "weather_state")
    for field in fields:
        target.set_editor_property(field, source.get_editor_property(field))
    actors[region_id].set_environment_state(target)
    result.setdefault("transition_river_weather", []).append({
        "time": now, **{field: target.get_editor_property(field) for field in fields[:-1]},
    })


def apply_transition_shortage(world, region="Highland"):
    migration = next((item for item in u.ObjectIterator(u.EcoHerdMigrationSubsystem) if item.get_outer() == world), None)
    if not migration or not migration.apply_food_fraction_for_audit(region, 0., True):
        raise RuntimeError(f"Could not apply the trial's explicit {region} forage shortage")
    if region == "Highland":
        result["transition_founder"]["pressure"] = "Highland Native forage stock drained once, regeneration suspended"


def check_transition_checkpoint(world, runtime, now):
    slot = result["transition_checkpoint_slot"]
    evidence = out.parent / "IslandAccessBaseline" / f"{slot}_snapshot.json"
    mode = result["transition_checkpoint"]
    if mode == "Save":
        founder = result["transition_founder"]
        agent = read_agent(world, founder["id"])
        entry = next((event for event in agent.get("gameplay_reason_history", ())
                      if event["reason"] == "PassageTransitEntered"), None) if agent else None
        if not entry or agent["region"] != result["transition_authoring"]["region_id"] or now < entry["time"] + 15.:
            if now > 155.:
                raise RuntimeError("Founder did not reach the interior of the corridor in time to save")
            return False
        if not runtime.save_ecosystem(slot):
            return False
        entered_at = entry["time"]
    else:
        if now < 4.:
            return False
        expected = json.loads(evidence.read_text(encoding="utf-8"))
        founder = expected["founder"]
        if not runtime.load_ecosystem(slot):
            raise RuntimeError(f"Could not restore {slot}")
        result["transition_founder"] = founder
        entered_at = expected["entered_at"]
    agents = {}
    for stable_id in inspect.get_authority_agent_ids(world):
        row = read_agent(world, stable_id)
        agents[str(stable_id)] = {key: row[key] for key in ("species", "region", "position", "hp", "energy")}
    stocks = {}
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        name = str(patch.get_editor_property("id"))
        stock = runtime.inspect_fauna_habitat_stock(name)
        stocks[name] = stock[-1] if isinstance(stock, tuple) else stock
    snapshot = {"founder": {key: founder[key] for key in ("id", "position_cm", "pressure")},
                "entered_at": entered_at, "agents": agents, "stocks": stocks}
    if mode == "Save":
        evidence.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    elif snapshot != expected:
        raise RuntimeError("Restored positions, residents, vitals or food stocks differ from the saved snapshot")
    result["transition_checkpoint_state"] = snapshot
    if result.get("transition_blocked_exit"):
        route, = (r for r in u.GameplayStatics.get_all_actors_of_class(world, u.EcoHerdMigrationRoute)
                  if str(r.get_editor_property("from_region")) == "Riverbank"
                  and str(r.get_editor_property("to_region")) == result["transition_authoring"]["region_id"])
        route.set_editor_property("enabled", False)
        result["transition_closed_route"] = route.get_name()
    if result.get("transition_wall"):
        wall, = u.GameplayStatics.get_all_actors_with_tag(world, "JYU.TransitCollisionWall")
        wall.static_mesh_component.set_collision_enabled(u.CollisionEnabled.QUERY_ONLY)
        wall.set_actor_enable_collision(True)
        endpoints = result["transition_region"]["seams"]["Riverbank"]["endpoints_cm"]
        first, last = (u.Vector(*p) for p in endpoints)
        midpoint = (first + last) * .5
        wall.set_actor_location(midpoint + u.Vector(0., 0., 140.), False, True)
        if u.EcoCreatureAnimationBuilder.validate_fauna_ground_segment(
                world, "None", "Bighorn", midpoint + (first - last) * 8., midpoint + (last - first) * 8., 1.):
            raise RuntimeError("The collision wall did not block the physical seam")
        result["transition_collision_wall"] = wall.get_name()
    return mode == "Save"


def transition_region_ledger(world):
    summary = u.GameplayStatics.get_game_state(world).get_ecology_summary()
    wanted = {"Highland", result["transition_authoring"]["region_id"], "Riverbank"}
    regions = {}
    for state in summary.get_editor_property("regions"):
        name = str(state.get_editor_property("region_id"))
        if name in wanted:
            regions[name] = {key: state.get_editor_property(key) for key in
                             ("population", "outbound_count", "incoming_count", "migration_in_count", "migration_out_count")}
    if regions.keys() != wanted:
        raise RuntimeError("The completed authority summary is missing a transit region")
    return regions


def compare_native_stage_bounds(world, runtime, now):
    # The saved island's four Native contexts use a 120 m stage. Run after the initial sample.
    stages = {"Snowfield": (20000., -10000.), "Grassland": (90000., 60000.),
              "Riverbank": (36500., 34800.), "Highland": (50700., 49500.)}
    regions = {str(actor.get_editor_property("region_id")): actor.get_editor_property("region_bounds")
               for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)}
    points = {}
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        name = str(patch.get_editor_property("id"))
        points[f"{name}:center"] = patch.get_editor_property("center")
        if patch.get_editor_property("has_shore_entry"):
            for field in ("water_entry_point", "shore_point", "dry_bank_point"):
                points[f"{name}:{field}"] = patch.get_editor_property(field)
        for i, point in enumerate(patch.get_editor_property("forage_access_points")):
            points[f"{name}:access:{i}"] = point
    for route in u.GameplayStatics.get_all_actors_of_class(world, u.EcoHerdMigrationRoute):
        for i, point in enumerate(route.get_editor_property("points")):
            points[f"{route.get_name()}:{i}"] = point

    def membership(point):
        members = []
        for name, bounds in sorted(regions.items()):
            local = u.MathLibrary.inverse_transform_location(bounds.get_world_transform(), point)
            extent = bounds.get_unscaled_box_extent()
            if all(abs(p) <= e for p, e in zip(local.to_tuple(), extent.to_tuple())):
                members.append(name)
        return members

    before = {name: membership(point) for name, point in points.items()}
    changes = {}
    snow_only = "-EcoIslandTrialSnowStageBounds" in command.split()
    selected_region = stage_bounds_trial[1] if stage_bounds_trial else (
        "Grassland" if "-EcoIslandTrialGrasslandStageBounds" in command.split() else None)
    separated = selected_region or "-EcoIslandTrialSeparatedStageBounds" in command.split()

    def world_aabb(bounds):
        transform = bounds.get_world_transform()
        extent = bounds.get_unscaled_box_extent()
        corners = [u.MathLibrary.transform_location(transform, u.Vector(i * extent.x, j * extent.y, k * extent.z)).to_tuple()
                   for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
        return tuple((min(axis), max(axis)) for axis in zip(*corners))

    def intersection(a, b):
        return math.prod(max(0., min(ahi, bhi) - max(alo, blo)) for (alo, ahi), (blo, bhi) in zip(a, b))

    boxes = {name: world_aabb(bounds) for name, bounds in regions.items()} if separated else {}
    for name, (x, y) in stages.items():
        if ((snow_only and name != "Snowfield") or (separated and name == "Snowfield")
                or (selected_region and name != selected_region)):
            continue
        bounds = regions[name]
        center = bounds.get_world_location()
        extent = bounds.get_unscaled_box_extent()
        rotation = bounds.get_world_rotation()
        if any(abs(angle) > .01 for angle in (rotation.pitch, rotation.yaw, rotation.roll)) or any(
            abs(scale - 1.) > .01 for scale in bounds.get_world_scale().to_tuple()
        ):
            raise RuntimeError(f"{name} needs an axis-aligned unscaled box for the boundary comparison")
        if abs(center.x - x) > 1. or abs(center.y - y) > 1.:
            raise RuntimeError(f"{name} moved away from the surveyed Native stage center")
        new_center = center
        if separated:
            old_box = boxes[name]
            neighbors = [(box, intersection(old_box, box)) for other, box in boxes.items() if other != name]
            protected = [point.to_tuple() for key, point in points.items() if name not in before[key]]
            options = [range(0, max(0, round(6000. - extent.x)) + 1, 300)] * 2
            options += [range(0, max(0, round(6000. - extent.y)) + 1, 300)] * 2
            best_box = old_box
            best_score = (4. * extent.x * extent.y, 0.)
            for west, east, south, north in product(*options):
                xl, xh = old_box[0][0] - west, old_box[0][1] + east
                yl, yh = old_box[1][0] - south, old_box[1][1] + north
                zl, zh = old_box[2]
                candidate = ((xl, xh), (yl, yh), (zl, zh))
                score = ((xh - xl) * (yh - yl), -abs(east - west) - abs(north - south))
                if score <= best_score or any(intersection(candidate, box) > previous + 1. for box, previous in neighbors):
                    continue
                if any(xl <= px <= xh and yl <= py <= yh and zl <= pz <= zh for px, py, pz in protected):
                    continue
                best_box, best_score = candidate, score
            boxes[name] = best_box
            new_center = u.Vector(*((lo + hi) * .5 for lo, hi in best_box))
            new_extent = u.Vector(*((hi - lo) * .5 for lo, hi in best_box))
        else:
            new_extent = u.Vector(max(extent.x, 6000.), max(extent.y, 6000.), extent.z)
        bounds.set_box_extent(new_extent, False)
        if separated:
            bounds.set_world_location(new_center, False, True)
        changes[name] = {"center_cm": list(center.to_tuple()), "before_extent_cm": list(extent.to_tuple()),
                         "after_center_cm": list(new_center.to_tuple()),
                         "after_extent_cm": list(bounds.get_unscaled_box_extent().to_tuple())}
    after = {name: membership(point) for name, point in points.items()}
    return {"pie_seconds": now, "regions": changes, "surveyed_points": len(points),
            "changed_membership": {name: {"before": before[name], "after": members}
                                   for name, members in after.items() if members != before[name]}}


def survey_region_seams(world):
    builder = u.EcoCreatureAnimationBuilder
    regions = {}
    for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion):
        name = str(actor.get_editor_property("region_id"))
        bounds = actor.get_editor_property("region_bounds")
        transform = bounds.get_world_transform()
        extent = bounds.get_unscaled_box_extent()
        regions[name] = (transform, extent, sorted(str(x) for x in actor.get_editor_property("adjacent_region_ids")))

    def contains(point, shape):
        transform, extent, _ = shape
        p = u.MathLibrary.inverse_transform_location(transform, point)
        return abs(p.x) <= extent.x and abs(p.y) <= extent.y and abs(p.z) <= extent.z

    def outline(shape):
        transform, extent, _ = shape
        perimeter = []
        for sign in (-1., 1.):
            for i in range(17):
                t = i / 8. - 1.
                for x, y in ((sign * extent.x, t * extent.y), (t * extent.x, sign * extent.y)):
                    perimeter.append(u.MathLibrary.transform_location(transform, u.Vector(x, y, 0.)))
        return perimeter

    def inside(point, shape):
        transform, extent, _ = shape
        local = u.MathLibrary.inverse_transform_location(transform, point)
        inset = u.Vector(max(-extent.x + 180., min(extent.x - 180., local.x)),
                         max(-extent.y + 180., min(extent.y - 180., local.y)), 0.)
        return u.MathLibrary.transform_location(transform, inset)

    outlines = {name: outline(shape) for name, shape in regions.items()}
    pairs = []
    for a, b in combinations(sorted(regions), 2):
        shape_a, shape_b = regions[a], regions[b]
        proposals = sorted(
            ((math.hypot(p.x - q.x, p.y - q.y), p, q) for p in outlines[a] for q in outlines[b]),
            key=lambda row: row[0])
        gap, _, _ = proposals[0]
        selected = []
        for distance, p, q in proposals:
            if distance > gap + 1800. or len(selected) == 10:
                break
            if any((p - old_p).length() < 420. and (q - old_q).length() < 420. for old_p, old_q in selected):
                continue
            selected.append((p, q))
        samples = []
        for p, q in selected:
            start, end = inside(p, shape_a), inside(q, shape_b)
            distance = math.hypot(start.x - end.x, start.y - end.y)
            segments = max(1, math.ceil(distance / 250.))
            if segments > 160:
                continue
            ground = [builder.project_placement_point(world, start + (end - start) * (i / segments))
                      for i in range(segments + 1)]
            row = {"start_hint": list(start.to_tuple()), "end_hint": list(end.to_tuple()),
                   "distance_cm": distance, "missing_ground": sum(p is None for p in ground)}
            if not row["missing_ground"]:
                owners = [[name for name, shape in regions.items() if contains(p, shape)] for p in ground]
                legs = list(zip(ground, ground[1:]))
                row.update({
                    "endpoints_cm": [list(p.to_tuple()) for p in (ground[0], ground[-1])],
                    "endpoint_regions": [owners[0], owners[-1]],
                    "unassigned_samples": sum(not names for names in owners),
                    "overlapping_samples": sum(len(names) > 1 for names in owners),
                    "elevation_range_cm": max(p.z for p in ground) - min(p.z for p in ground),
                    "swept_both_directions": all(builder.validate_habitat_ground_segment(world, first, last)
                                                and builder.validate_habitat_ground_segment(world, last, first)
                                                for first, last in legs),
                })
                if (a, b) in (("Highland", "Riverbank"), ("Grassland", "LowerRiver")):
                    row["fauna_round_trip"] = {
                        species: {str(scale): all(builder.validate_fauna_ground_segment(world, "None", species, first, last, scale)
                                                 and builder.validate_fauna_ground_segment(world, "None", species, last, first, scale)
                                                 for first, last in legs)
                                  for scale in (.6, 1.)}
                        for species in ("Rat", "Bighorn", "Horse", "Buffalo", "Fox", "Mink")
                    }
            samples.append(row)
        pairs.append({"regions": [a, b], "closest_sampled_perimeter_cm": gap, "corridors": samples})
    if len(regions) < 2 or not any(row["corridors"] for row in pairs):
        raise RuntimeError("No island region corridors sampled")
    routes = u.GameplayStatics.get_all_actors_of_class(world, u.EcoHerdMigrationRoute)
    return {"regions": {name: {"center_cm": list(transform.translation.to_tuple()),
                               "extent_cm": list(extent.to_tuple()), "adjacent": adjacent}
                        for name, (transform, extent, adjacent) in regions.items()},
            "rule_route_count": sum(bool(route.get_editor_property("bAllowRuleFaunaPassage")) for route in routes),
            "pairs": pairs}


def survey_eagle_geometry(world, runtime):
    builder = u.EcoCreatureAnimationBuilder
    profiles = {str(p.get_editor_property("species_id")): p for p in runtime.get_editor_property("fauna_species")}
    eagle, rat = profiles["GoldenEagle"], profiles["Rat"]
    eye = eagle.get_editor_property("eye_height")
    prey_eye = rat.get_editor_property("eye_height")
    sweep = max(4., eagle.get_editor_property("body_radius") * .45)
    reach = eagle.get_editor_property("attack_reach")
    static = [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1]
    cube = u.load_asset("/Engine/BasicShapes/Cube")
    rows = []
    for hint in highland_near_cover_sites:
        prey = builder.project_placement_point(world, u.Vector(*hint))
        if prey is None:
            raise RuntimeError("Eagle geometry trial could not project a Highland prey point")
        start = prey + u.Vector(-700., 0., 1500.)
        end = prey + u.Vector(0., 0., reach * .38)
        eye_start = start + u.Vector(0., 0., eye)
        eye_end = prey + u.Vector(0., 0., prey_eye)
        for kind in ("clear", "sight_only", "body_only", "solid"):
            obstacle = None
            actor = None
            if kind != "clear":
                midpoint = (eye_start + eye_end) * .5 if kind != "body_only" else (start + end) * .5
                if kind == "body_only":
                    midpoint += u.Vector(0., 12. + sweep * .5, 0.)
                actor = builder.spawn_visual_audit_actor(world, u.StaticMeshActor, u.Transform(location=midpoint))
                if actor is None:
                    raise RuntimeError("Eagle geometry trial could not place its temporary cover")
                component = actor.static_mesh_component
                component.set_mobility(u.ComponentMobility.MOVABLE)
                component.set_static_mesh(cube)
                component.set_collision_profile_name("EcoFaunaSightCoverQuery" if kind == "sight_only" else "BlockAll")
                actor.set_actor_scale3d(u.Vector(.24, .24, .24))
                obstacle = {"center_cm": list(midpoint.to_tuple()), "half_extent_cm": 12., "physical": kind != "sight_only"}
            try:
                clear = builder.has_fauna_audit_sight(world, eye_start, eye_end)
                body_blocked = bool(u.SystemLibrary.sphere_trace_single_for_objects(
                    world, start, end, sweep, static, False, [], u.DrawDebugTrace.NONE, True))
                rows.append({"case": kind, "start_cm": list(start.to_tuple()), "prey_cm": list(prey.to_tuple()),
                             "contact_cm": list(end.to_tuple()), "obstacle": obstacle, "clear": clear, "body_blocked": body_blocked})
            finally:
                if actor is not None:
                    actor.set_actor_enable_collision(False)
                    actor.destroy_actor()
    return {"eye_cm": eye, "prey_eye_cm": prey_eye, "sweep_radius_cm": sweep, "attack_reach_cm": reach, "rows": rows}


def survey_highland_cover(world, runtime):
    builder = u.EcoCreatureAnimationBuilder
    anchors = [u.Vector(*site) for site in authored["dry_refuges"][-2:]]
    refuges = u.GameplayStatics.get_all_actors_of_class(world, u.EcoRefugeHabitat)
    refuges = [min(refuges, key=lambda a: (a.get_actor_location() - point).length()) for point in anchors]
    if len(set(a.get_name() for a in refuges)) != 2:
        raise RuntimeError("Expected two different highland refuges")
    boulders = [a.get_editor_property("boulders") for a in refuges]
    if result["cover_trial"] == "Boulders":
        for component in boulders:
            component.set_collision_profile_name("BlockAll")
    elif result["cover_trial"] == "Sight":
        for refuge in refuges:
            refuge.set_fauna_boulder_occlusion(True)

    def sight_hit(start, target):
        hit = u.SystemLibrary.line_trace_single_for_objects(
            world, start, target, [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True)
        if not hit:
            return None if builder.has_fauna_audit_sight(world, start, target) else "SightCover"
        component = hit.to_tuple()[10]
        return "Boulder" if component in boulders else "OtherWorldStatic"

    def connected(start, destination, scale):
        return builder.validate_fauna_ground_segment(world, "Highland", "Rat", start, destination, scale)

    rat, = (profile for profile in runtime.get_editor_property("fauna_species")
            if str(profile.get_editor_property("species_id")) == "Rat")
    eye = rat.get_editor_property("eye_height")
    rows = []
    for refuge_index, component in enumerate(boulders):
        mesh = component.get_editor_property("static_mesh")
        box = mesh.get_bounding_box()
        for i in range(component.get_instance_count()):
            transform = component.get_instance_transform(i, True)
            rock = u.MathLibrary.transform_location(transform, (box.min + box.max) * .5)
            for direction in range(8):
                angle = direction * math.tau / 8.
                forward = u.Vector(math.cos(angle), math.sin(angle), 0.)
                side = u.Vector(-forward.y, forward.x, 0.)
                hidden = builder.project_placement_point(world, rock + forward * 170.)
                if hidden is None:
                    continue
                target = hidden + u.Vector(0., 0., eye)
                exits = [builder.project_placement_point(world, hidden + offset)
                         for offset in (forward * 220., side * 220., side * -220.)]
                rows.append({
                    "refuge": refuge_index, "rock": i, "direction": direction,
                    "target": list(hidden.to_tuple()),
                    "low_sight": sight_hit(rock - forward * 450. + u.Vector(0., 0., 30.), target),
                    "descending_sight": sight_hit(rock - forward * 450. + u.Vector(0., 0., 360.), target),
                    "vertical_sight": sight_hit(target + u.Vector(0., 0., 500.), target),
                    "exit_count": {str(scale): sum(p is not None and connected(hidden, p, scale)
                                                   and connected(p, hidden, scale) for p in exits)
                                   for scale in (.6, 1.)},
                })
    if not rows:
        raise RuntimeError("No refuge sightlines sampled")
    candidates = [u.Vector(*row["target"]) for row in rows
                  if row["descending_sight"] in ("Boulder", "SightCover") and row["exit_count"]["1.0"] >= 2]
    routes = []
    starts = highland_near_cover_sites if result.get("near_cover") else highland_rat_sites
    for start in (u.Vector(*site) for site in starts):
        route = None
        for candidate in sorted(candidates, key=lambda p: (p - start).length()):
            distance = (candidate - start).length()
            segments = max(1, math.ceil(distance / 300.))
            points = [builder.project_placement_point(world, start + (candidate - start) * (i / segments))
                      for i in range(segments + 1)]
            if any(p is None for p in points):
                continue
            legs = list(zip(points, points[1:]))
            if all(connected(a, b, scale) and connected(b, a, scale)
                   for a, b in legs for scale in (.6, 1.)):
                length = sum((b - a).length() for a, b in legs)
                route = {"target_cm": list(candidate.to_tuple()), "length_cm": length,
                         "uninterrupted_walk_seconds": length / rat.get_editor_property("walk_speed")}
                break
        routes.append(route)
    return {"boulder_counts": [c.get_instance_count() for c in boulders], "rays": rows,
            "founder_screened_ground_routes": routes,
            "founder_distance_to_screened_exit_cm": [
                min(((u.Vector(*start) - candidate).length() for candidate in candidates), default=None)
                for start in starts
            ]}


def sample_highland_eagle_cover(world, runtime, now):
    trial = result["eagle_prey_layout"]
    summary = u.GameplayStatics.get_game_state(world).get_ecology_summary()
    authority = summary.get_editor_property("time").get_editor_property("server_time_seconds")
    rows = {}
    for agent in (*trial["moved_rat_ids"], *trial["eagle_ids"]):
        row = read_agent(world, agent)
        if row and row["hp"] > 0:
            rows[agent] = row
            result.setdefault("near_cover_tracks", []).append({
                "time": now, "completed_authority_seconds": authority, "id": agent, "position": row["position"],
                "activity": row.get("activity"), "energy": row["energy"],
                "rule_fauna": row.get("rule_fauna", {}),
            })
    if "eagle_cover_profile" not in trial:
        profiles = {str(profile.get_editor_property("species_id")): profile
                    for profile in runtime.get_editor_property("fauna_species")}
        eagle, rat = profiles["GoldenEagle"], profiles["Rat"]
        rule, = (rule for rule in eagle.get_editor_property("prey_rules")
                 if str(rule.get_editor_property("species_id")) == "Rat")
        limit = rule.get_editor_property("max_pursuit_start")
        reach = eagle.get_editor_property("sight_range")
        trial["eagle_cover_profile"] = {
            "eagle_eye_cm": eagle.get_editor_property("eye_height"), "rat_eye_cm": rat.get_editor_property("eye_height"),
            "within_range_cm": min(reach, limit) if limit > 0. else reach,
            "attack_reach_cm": eagle.get_editor_property("attack_reach"),
            "cruise_height_cm": eagle.get_editor_property("flight_cruise_height"),
            "baseline_sight_rays": "Actual sampled positions, no energy or facing filter",
        }
    profile = trial["eagle_cover_profile"]
    locations = {agent: u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", row["position"])))
                 for agent, row in rows.items()}
    if refuge := result.get("rat_refuge_trial"):
        center = runtime.get_editor_property("fauna_habitat_patches")[refuge["patch_index"]].get_editor_property("center")
        for rat in trial["moved_rat_ids"]:
            if rat not in rows or not str(rows[rat]["activity"]).endswith("::Flee"):
                continue
            position = locations[rat]
            distance = (center - position).length()
            unobstructed = static_clear = None
            if distance < 650.:
                start = position + u.Vector(0., 0., profile["rat_eye_cm"])
                end = center + u.Vector(0., 0., 5.)
                unobstructed = u.EcoCreatureAnimationBuilder.has_fauna_audit_sight(world, start, end)
                static_clear = not bool(u.SystemLibrary.line_trace_single_for_objects(
                    world, start, end, [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True))
            result.setdefault("rat_refuge_flee_sight", []).append({
                "rat": rat, "world_seconds": now, "completed_authority_seconds": authority,
                "distance_cm": distance, "within_search_radius": distance < 650.,
                "clear_fauna_sight": unobstructed, "clear_world_static": static_clear,
                "selected_patch_index": rows[rat]["rule_fauna"]["food_patch_index"],
            })
    for eagle in trial["eagle_ids"]:
        if eagle not in rows or rows[eagle]["rule_fauna"]["flight_phase"] != 2:
            continue
        for rat in trial["moved_rat_ids"]:
            if rat not in rows or rows[rat]["region"] != rows[eagle]["region"]:
                continue
            start, destination = locations[eagle], locations[rat]
            span = (start - destination).length()
            high = start.z - destination.z
            if span > profile["within_range_cm"] or not profile["attack_reach_cm"] <= high <= profile["cruise_height_cm"]:
                continue
            ray_start = start + u.Vector(0., 0., profile["eagle_eye_cm"])
            ray_end = destination + u.Vector(0., 0., profile["rat_eye_cm"])
            clear = u.EcoCreatureAnimationBuilder.has_fauna_audit_sight(world, ray_start, ray_end)
            blocked_static = not clear and bool(u.SystemLibrary.line_trace_single_for_objects(
                world, ray_start, ray_end, [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True))
            result.setdefault("eagle_cover_sight_samples", []).append({
                "time": now, "completed_authority_seconds": authority,
                "eagle": eagle, "rat": rat, "distance_cm": span, "elevation_delta_cm": high,
                "clear": clear, "blocked_world_static": blocked_static,
            })


def survey_highland_ground(world, runtime):
    builder = u.EcoCreatureAnimationBuilder
    region = "Highland"
    group, = (g for g in runtime.get_editor_property("groups") if str(g.get_editor_property("region_id")) == region)
    center = group.get_editor_property("food_patch_position")
    stride = 300.
    half_width = 8
    grid = {}
    for x in range(-half_width, half_width + 1):
        for y in range(-half_width, half_width + 1):
            point = builder.project_placement_point(world, center + u.Vector(x * stride, y * stride, 0.))
            if point is not None:
                grid[x, y] = point
    patches = {str(p.get_editor_property("id")): p
               for p in runtime.get_editor_property("fauna_habitat_patches")
               if str(p.get_editor_property("region_id")) == region and not p.get_editor_property("submerged")}
    starts = {f"BighornFounder{i}": point
              for placement in group.get_editor_property("fauna")
              if str(placement.get_editor_property("species_id")) == "Bighorn"
              for i, point in enumerate(placement.get_editor_property("spawn_points"), start=1)}
    starts.update({f"RatCandidate{i}": u.Vector(*site) for i, site in enumerate(highland_rat_sites, start=1)})
    outcomes = []
    for species in ("Rat", "Bighorn", "Horse", "Buffalo"):
        for scale in (.6, 1.):
            def passes(start, end):
                return builder.validate_fauna_ground_segment(world, region, species, start, end, scale)

            links = {cell: [] for cell in grid}
            for (x, y), point in grid.items():
                for adjacent in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if adjacent in grid and passes(point, grid[adjacent]):
                        links[x, y].append(adjacent)
            entrances = {}
            edible = set()
            for name, patch in patches.items():
                site = patch.get_editor_property("center")
                entrances[name] = {cell for cell, point in grid.items()
                                   if math.hypot(site.x - point.x, site.y - point.y) <= stride and passes(point, site)}
                if species in {str(consumer) for consumer in patch.get_editor_property("consumers")}:
                    edible.add(name)
            relevant_starts = {name: site for name, site in starts.items() if name.startswith(species)}
            for name, site in (relevant_starts or {"Reference": center}).items():
                reachable = {cell for cell, point in grid.items()
                             if math.hypot(site.x - point.x, site.y - point.y) <= stride and passes(site, point)}
                frontier = list(reachable)
                while frontier:
                    additions = set(links[frontier.pop()]) - reachable
                    reachable.update(additions)
                    frontier.extend(additions)
                connected_patches = {name for name, nodes in entrances.items() if nodes & reachable}
                outcomes.append({"species": species, "body_scale": scale, "start": name,
                                 "reachable_nodes": len(reachable),
                                 "surface_area_proxy_m2": len(reachable) * (stride / 100.) ** 2,
                                 "reachable_patch_centers": sorted(connected_patches),
                                 "reachable_edible_patches": sorted(connected_patches & edible)})
    return {"grid_stride_cm": stride, "grid_nodes": len(grid), "grid_max_nodes": (2 * half_width + 1) ** 2,
            "center": list(center.to_tuple()), "results": outcomes}


def apply_eagle_prey_trial(world, runtime):
    groups = [group.copy() for group in runtime.get_editor_property("groups")]
    by_region = {str(group.get_editor_property("region_id")): group for group in groups}
    riverbank, highland = (by_region[name] for name in ("Riverbank", "Highland"))
    original = [row.copy() for row in riverbank.get_editor_property("fauna")]
    rats, = (row for row in original if str(row.get_editor_property("species_id")) == "Rat")
    points = list(rats.get_editor_property("spawn_points"))
    if len(points) != 6:
        raise RuntimeError("Expected six existing riverbank rat founders")
    upland = [row.copy() for row in highland.get_editor_property("fauna")]
    eagles, = (row for row in upland if str(row.get_editor_property("species_id")) == "GoldenEagle")
    left, _ = eagles.get_editor_property("spawn_points")
    sites = []
    for offset in (u.Vector(-540., -310., 0.), u.Vector(700., -530., 0.)):
        point = u.EcoCreatureAnimationBuilder.project_placement_point(world, left + offset)
        if point is None:
            raise RuntimeError("Trial rat founder has no Highland ground")
        sites.append(point)
    rats.set_editor_property("spawn_points", points[:-len(sites)])
    moved = rats.copy()
    moved.set_editor_property("spawn_points", sites)
    riverbank.set_editor_property("fauna", original)
    highland.set_editor_property("fauna", [*upland, moved])
    runtime.set_editor_property("groups", groups)
    result["eagle_prey_layout"] = {"riverbank_count": len(points) - len(sites),
                                   "highland_sites": [list(point.to_tuple()) for point in sites]}


def apply_eagle_fixed_id_trial(world, runtime):
    rows = [read_agent(world, agent) for agent in inspect.get_authority_agent_ids(world)]
    rats = sorted(int(row["stable_id"]) for row in rows if row["species"] == "Rat" and row["region"] == "Riverbank")
    if len(rats) != 6:
        raise RuntimeError("Expected six existing riverbank rat founders")
    moved = []
    sites = highland_near_cover_sites if result.get("near_cover") else highland_rat_sites
    for agent, site in zip(rats[-len(sites):], sites):
        if not u.EcoCreatureAnimationBuilder.set_island_audit_founder_placement(runtime, agent, "Highland", u.Vector(*site)):
            raise RuntimeError(f"Could not place rat {agent} before its first decision")
        moved.append(agent)
    result["eagle_prey_layout"] = {"moved_rat_ids": moved,
                                   "sites_cm": sites,
                                   "eagle_ids": sorted(int(row["stable_id"]) for row in rows if row["species"] == "GoldenEagle")}


def apply_rat_refuge_trial(world, runtime, mode):
    geometry = u.EcoCreatureAnimationBuilder
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    source, = (patch for patch in patches if str(patch.get_editor_property("id")) == "IslandForageUplandForbs")
    destination = geometry.project_placement_point(world, u.Vector(*highland_near_cover_sites[0]))
    if destination is None or any(not geometry.validate_fauna_ground_segment(
            world, "Highland", "Rat", u.Vector(*start), destination, 1.) for start in highland_near_cover_sites):
        raise RuntimeError("The refuge trial site needs a dry ground approach from both rat founders")
    # Use the existing habitat representation and debit the same stock in both arms.
    # The site accepts the donor's consumers, so a rat cannot eat from it.
    site = u.EcoFaunaHabitatPatch()
    for key, value in {"id": "IslandAuditRatRefuge", "region_id": "Highland", "center": destination,
                       "consumers": source.get_editor_property("consumers"), "capacity": 0.125,
                       "energy_per_meal": source.get_editor_property("energy_per_meal")}.items():
        site.set_editor_property(key, value)
    if "Rat" in {str(kind) for kind in site.get_editor_property("consumers")}:
        raise RuntimeError("The refuge fixture must preserve rat access to existing food only")
    source.set_editor_property("capacity", source.get_editor_property("capacity") - 0.125)
    entrance = 0.
    if mode in ("Target", "Narrow"):
        site.set_editor_property("sheltered_species", "Rat")
        site.set_editor_property("shelter_radius", 65.)
        # Target retains ordinary capture checks. Narrow uses the earlier fauna burrow threshold.
        entrance = 7. if mode == "Narrow" else 100.
        site.set_editor_property("entrance_radius", entrance)
    runtime.set_editor_property("fauna_habitat_patches", [*patches, site])
    return {"mode": mode, "patch_index": len(patches), "center_cm": list(destination.to_tuple()),
            "radius_cm": 65., "entrance_radius_cm": entrance, "capacity_debited": .125}


def apply_river_rat_refuge_trial(world, runtime, mode, persist=False):
    geometry = u.EcoCreatureAnimationBuilder
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    source, = (patch for patch in patches if str(patch.get_editor_property("id")) == "IslandForageWestForbs")
    if "Rat" in map(str, source.get_editor_property("consumers")):
        raise RuntimeError("Riverbank refuge trial requires a donor without rat feeding access")
    if persist and any(str(patch.get_editor_property("id")).startswith("IslandRiverRatRefuge") for patch in patches):
        raise RuntimeError("Riverbank rat refuges already exist on this island")
    # The near pair moves the same two sites toward the measured aborted approaches.
    locations = ((37710., 35870.), (37880., 36280.)) if mode.startswith(("Near", "Aligned", "Approach")) else (
        (38050., 36050.), (38000., 36550.))
    sites = []
    for x, y in locations:
        point = geometry.project_placement_point(world, u.Vector(x, y, 3100.))
        if point is None:
            raise RuntimeError("No ground at Riverbank refuge candidate")
        site = u.EcoFaunaHabitatPatch()
        prefix = "IslandRiverRatRefuge" if persist else "IslandAuditRiverRatRefuge"
        for key, value in {"id": f"{prefix}{len(sites)}", "region_id": "Riverbank", "center": point,
                           "consumers": source.get_editor_property("consumers"), "capacity": .125,
                           "energy_per_meal": source.get_editor_property("energy_per_meal")}.items():
            site.set_editor_property(key, value)
        if mode.endswith(("Narrow", "Covered")):
            site.set_editor_property("sheltered_species", "Rat")
            site.set_editor_property("shelter_radius", 65.)
            site.set_editor_property("entrance_radius", 7.)
        if mode == "ApproachCovered":
            axis = u.MathLibrary.get_forward_vector(u.Rotator(0., 0., (75., 100.)[len(sites)]))
            first_mouth = -180. if river_rat_shift_mouth and not sites else -160.
            site.set_editor_property("shelter_approach_points", [point + axis * offset for offset in (first_mouth, 160.)])
        sites.append({"patch_index": len(patches), "center_cm": list(point.to_tuple())})
        patches.append(site)
    if persist:
        runtime.modify()
    source.set_editor_property("capacity", source.get_editor_property("capacity") - .125 * len(sites))
    runtime.set_editor_property("fauna_habitat_patches", patches)
    return {"mode": mode, "sites": sites, "samples": []}


def measure_river_rat_cover(world, runtime, sites, aligned, *, spawn=True, persist=False):
    geometry = u.EcoCreatureAnimationBuilder
    profiles = {str(profile.get_editor_property("species_id")): profile
                for profile in runtime.get_editor_property("fauna_species")}
    bodies = {species: {field + "_cm": profiles[species].get_editor_property(field)
                        for field in ("body_radius", "sweep_height", "step_height")}
              for species in ("Rat", "Fox")}
    measurements = []
    for site, yaw in zip(sites, (75., 100.) if aligned else (0., 0.), strict=True):
        center = u.Vector(*site["center_cm"])
        rotation = u.Rotator(0., 0., yaw)
        axis = u.MathLibrary.get_forward_vector(rotation)
        side = u.MathLibrary.get_right_vector(rotation)
        mouths = [center + axis * offset for offset in (-160., 160.)]
        for endpoint in mouths:
            floor = geometry.project_placement_point(world, endpoint)
            if floor is None or abs(floor.z - endpoint.z) > 1.:
                raise RuntimeError("Riverbank covered refuge needs dry, level mouth points")
        # Keep the enclosing collision above the rat's ground trace and below the fox's body sweep.
        if spawn:
            for part, dy, thickness, top, width in (("Roof", 0., 87., 100., 50.),
                    ("Left", -31., 100., 100., 12.), ("Right", 31., 100., 100., 12.)):
                actor = spawn_mink_walk_surface(world, center + side * dy + u.Vector(0., 0., top), rotation,
                                               u.Vector(1.30, width / 100., thickness / 100.), authored_actor=persist)
                if persist:
                    actor.set_actor_label(f"JYU_RiverRatRefuge_{site['patch_index']}_{part}")
        approaches = []
        for offset_along, offset_across in ((160., 0.), (0., 100.), (160., 100.)):
            start = center + axis * offset_along + side * offset_across
            approaches.append({"start_cm": list(start.to_tuple()), "direct": geometry.validate_fauna_ground_segment(
                world, "Riverbank", "Rat", start, center, 1.), "through_mouth": [
                geometry.validate_fauna_ground_segment(world, "Riverbank", "Rat", start, mouth, 1.)
                and geometry.validate_fauna_ground_segment(world, "Riverbank", "Rat", mouth, center, 1.)
                for mouth in mouths]})
        rat_profile = profiles["Rat"]
        eye_height = rat_profile.get_editor_property("eye_height")
        sight_cases = []
        for name, start, end in (
                ("through_wall", center, center + side * 100.),
                ("toward_mouth", center, mouths[1]),
                ("back_across_roof", center, center + axis * 100.),
                ("outside_mouth", mouths[1], mouths[1] + side * 100.),
                ("from_side_to_mouth", center + side * 100., mouths[1])):
            target_height = 5. if name == "toward_mouth" else 35.
            sight_cases.append({"case": name, "start_cm": list(start.to_tuple()), "end_cm": list(end.to_tuple()),
                "target_height_cm": target_height, "clear": geometry.has_fauna_audit_sight(
                    world, start + u.Vector(0., 0., eye_height), end + u.Vector(0., 0., target_height))})
        measurements.append({"site_index": site["patch_index"], "yaw_degrees": yaw,
            "mouths_cm": [list(p.to_tuple()) for p in mouths],
            "opening_cm": {"length": 130., "width": 50., "height": 13., "wall_thickness": 12.},
            "rat_vision": {field: rat_profile.get_editor_property(field) for field in (
                "eye_height", "night_vision", "threat_sense_range", "threat_sight_half_angle", "threat_near_awareness_range")},
            "sight_cases": sight_cases,
            "bodies": bodies, "rat_approaches": approaches,
            "crossings": {species: {str(scale): [geometry.validate_fauna_ground_segment(
                world, "Riverbank", species, start, end, scale) for start, end in (mouths, mouths[::-1])]
                for scale in (.6, 1.)} for species in ("Rat", "Fox")},
            "mouth_sight_to_center": {species: [geometry.has_fauna_audit_sight(
                world, p + u.Vector(0., 0., height), center + u.Vector(0., 0., 5.)) for p in mouths]
                for species, height in (("Rat", 5.), ("Fox", 50.))}})
    return measurements


def sample_river_rat_refuge(world, runtime, now):
    trial = result["river_rat_refuge"]
    geometry = u.EcoCreatureAnimationBuilder
    if (trial["mode"].endswith("Covered") or trial["mode"] == "Saved") and "physical_cover" not in trial:
        trial["physical_cover"] = measure_river_rat_cover(world, runtime, trial["sites"],
            trial["mode"] != "NearCovered", spawn=trial["mode"] != "Saved")
    summary = u.GameplayStatics.get_game_state(world).get_ecology_summary()
    authority = summary.get_editor_property("time").get_editor_property("server_time_seconds")
    foxes = {}
    for stable_id in (65, 66):
        fox = read_agent(world, stable_id)
        if fox and fox["species"] == "Fox" and fox["hp"] > 0.:
            foxes[stable_id] = list(map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", fox["position"])))
    rows = []
    for stable_id in range(72, 78):
        rat = read_agent(world, stable_id)
        if not rat or rat["hp"] <= 0. or rat["species"] != "Rat":
            continue
        xyz = list(map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", rat["position"])))
        if "founder_approaches" not in trial:
            point = u.Vector(*xyz)
            rows.append({"id": stable_id, "position_cm": xyz, "sites": [
                site["patch_index"] for site in trial["sites"]
                if geometry.validate_fauna_ground_segment(world, "Riverbank", "Rat", point, u.Vector(*site["center_cm"]), 1.)]})
        trial["samples"].append({"world_seconds": now, "completed_authority_seconds": authority,
                                 "id": stable_id, "position_cm": xyz, "fox_positions_cm": foxes,
                                 "activity": rat["activity"], "target": rat["rule_fauna"]["food_patch_index"],
                                 "gameplay_reasons": rat.get("gameplay_reason_history", [])})
        if not trial["mode"].endswith(("Narrow", "Covered", "Saved")) or "-EcoIslandNoCapture" in command.split():
            continue
        site = next((site for site in trial["sites"] if site["patch_index"] == rat["rule_fauna"]["food_patch_index"]), None)
        if site and "rat_refuge_entry_capture" not in trial and (u.Vector(*xyz) - u.Vector(*site["center_cm"])).length() <= 65.:
            center = u.Vector(*site["center_cm"])
            set_camera(world, center + u.Vector(260., -340., 230.), center)
            capture(world, "IslandFauna_RiverRatRefugeEntry")
            trial["rat_refuge_entry_capture"] = {"id": stable_id, "world_seconds": now, "site_cm": site["center_cm"]}
    if rows:
        trial["founder_approaches"] = rows


def check_island_checkpoint(world, runtime, now):
    mode = result["checkpoint_mode"]
    slot = result["checkpoint_slot"]
    evidence = out.parent / "IslandAccessBaseline" / f"{slot}_snapshot.json"
    if result["checkpoint_forage_soil"] and not runtime.get_editor_property("use_native_soil_for_fauna_forage"):
        raise RuntimeError("Forage soil must be enabled in the saved island")
    if "checkpoint_state" not in result:
        habitat_saved = result.get("transition_habitat_saved")
        if mode == "Save" and now < (65. if habitat_saved else 185. if water_forage_shared else 175.):
            return False
        if mode == "Save" and water_forage_shared:
            meals = drift_forage_payments(world, "IslandRiverDrift")
            if not meals:
                if now >= 190.:
                    raise RuntimeError("No shared water forage payment before the checkpoint")
                return False
            result["checkpoint_pre_save_shared_meals"] = meals
        if mode == "Save" and result["checkpoint_drift"] and not drift_forage_payments(world):
            if now >= 240.:
                raise RuntimeError("No Drift forage payment before the checkpoint")
            return False
        if mode == "Save" and habitat_saved:
            habitat_id = result["transition_authoring"]["region_id"]
            fed_resident = any(
                row and row["species"] == "Jackrabbit" and row["region"] == habitat_id and row["hp"] > 0.
                and any(event["reason"] == "HabitatPatchEaten" and event["region"] == habitat_id
                        for event in row.get("gameplay_reason_history", ()))
                for row in (read_agent(world, agent) for agent in inspect.get_authority_agent_ids(world))
            )
            if not fed_resident:
                if now >= 95.:
                    raise RuntimeError("No resident jackrabbit fed before the saved habitat checkpoint")
                return False
        if mode == "Load" and now < 4.:
            return False
        if mode == "Load":
            loaded = runtime.load_ecosystem(slot)
            if river_rat_shift_mouth:
                if loaded:
                    raise RuntimeError("Checkpoint accepted a shifted rat approach point")
                result["checkpoint_rejected_shifted_rat_mouth"] = True
                return True
            if not loaded:
                raise RuntimeError(f"Could not restore {slot}")
        if mode == "Save" and not runtime.save_ecosystem(slot):
            if now > 190.:
                raise RuntimeError(f"Could not save {slot} before the first hatch")
            return False
        snapshot = {"agents": {}, "stock": {}}
        river, = (actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)
                  if str(actor.get_editor_property("region_id")) == authored["river"])
        environment = river.get_editor_property("environment_state")
        snapshot["river_environment"] = {key: environment.get_editor_property(key)
                                         for key in ("temperature", "humidity", "rainfall")}
        snapshot["river_environment"]["weather"] = str(environment.get_editor_property("weather_state"))
        snapshot["river_environment"]["day_phase"] = str(environment.get_editor_property("day_phase"))
        for agent in inspect.get_authority_agent_ids(world):
            row = read_agent(world, agent)
            snapshot["agents"][str(agent)] = {key: row[key] for key in ("species", "region", "position", "hp", "energy")}
        for patch in runtime.get_editor_property("fauna_habitat_patches"):
            key = str(patch.get_editor_property("id"))
            stock = runtime.inspect_fauna_habitat_stock(key)
            snapshot["stock"][key] = stock[-1] if isinstance(stock, tuple) else stock
            if points := patch.get_editor_property("shelter_approach_points"):
                snapshot.setdefault("shelter_approach_points", {})[key] = [list(point.to_tuple()) for point in points]
            if water_forage_shared and (points := patch.get_editor_property("forage_access_points")):
                snapshot.setdefault("forage_access_points", {})[key] = [list(point.to_tuple()) for point in points]
        if water_forage_shared and not snapshot.get("forage_access_points", {}).get("IslandRiverDrift"):
            raise RuntimeError("Missing the shared Drift forage approach")
        if "-EcoIslandCheckpointFinalBank" in command.split():
            snapshot["wet_patch_geometry"] = {
                str(p.get_editor_property("id")): {
                    field: list(p.get_editor_property(field).to_tuple())
                    for field in ("center", "shore_point", "water_entry_point", "dry_bank_point")
                } for p in runtime.get_editor_property("fauna_habitat_patches")
                if p.get_editor_property("submerged")
            }
        if runtime.get_editor_property("use_native_soil_for_fauna_forage") or local_soil_trial:
            moisture = sample_forage_soil(runtime, snapshot["stock"])
            if not moisture:
                raise RuntimeError("Expected native soil for the saved island forage")
            if slot.startswith("IslandLocalForageSoil_") and not {
                    "IslandForageSouthBrowse", "IslandTransitionForbs"} <= moisture.keys():
                raise RuntimeError("Expected both river and transition local soil in the checkpoint")
            snapshot["forage_soil_moisture"] = moisture
        if result.get("meadow_layout") == "Shared":
            snapshot["shared_forage"] = result["meadow_trial"]
        if habitat_saved:
            sample = sample_saved_transition_habitat(world, runtime, now)
            snapshot["saved_habitat"] = {"climate": sample["climate"], "forage": sample["forage"],
                                         "ledger": transition_region_ledger(world)}
        result["checkpoint_state"] = snapshot
        if mode == "Save":
            evidence.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            return True
        expected = json.loads(evidence.read_text(encoding="utf-8"))
        if any(snapshot.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Restored agent, stock or environment state differs from the saved snapshot")
        result["checkpoint_environment_compared"] = "river_environment" in expected
        result["checkpoint_loaded_at"] = now
        if result["checkpoint_drift"]:
            result["checkpoint_initial_drift_meals"] = drift_forage_payments(world)
        if water_forage_shared:
            result["checkpoint_initial_shared_meals"] = drift_forage_payments(world, "IslandRiverDrift")
            if water_forage_drawdown:
                set_shared_forage_drawdown(world, runtime, now)
        return False
    if result["checkpoint_drift"]:
        before = {tuple(row) for row in result["checkpoint_initial_drift_meals"]}
        meals = [row for row in drift_forage_payments(world) if tuple(row) not in before]
        if meals:
            result["checkpoint_resumed_drift_meals"] = meals
            return True
        if now >= result["checkpoint_loaded_at"] + 60.:
            raise RuntimeError("No new Drift forage payment after restoring")
        return False
    if result.get("transition_habitat_saved"):
        habitat = result["transition_authoring"]["region_id"]
        residents = {int(agent) for agent, row in result["checkpoint_state"]["agents"].items()
                     if row["species"] == "Jackrabbit" and row["region"] == habitat and row["hp"] > 0.}
        meals = [(agent, event["time"], event["amount"]) for agent in residents
                 for event in (read_agent(world, agent) or {}).get("gameplay_reason_history", ())
                 if event["reason"] == "HabitatPatchEaten" and event["region"] == habitat]
        if meals:
            result["checkpoint_resumed_habitat_meals"] = sorted(meals)
            return True
        if now >= result["checkpoint_loaded_at"] + 30.:
            raise RuntimeError("No resident jackrabbit fed in the restored transition habitat")
        return False
    if water_forage_drawdown:
        drawdown = result["shared_forage_drawdown"]
        if "restored" not in drawdown and now >= result["checkpoint_loaded_at"] + 20.:
            set_shared_forage_drawdown(world, runtime, now)
        if "restored" not in drawdown or now < drawdown["restored"]["world_seconds"] + 25.:
            return False
    if now < result["checkpoint_loaded_at"] + 25.:
        return False
    if result.get("meadow_layout") == "Shared":
        return True
    hatches = {event["related_id"] for agent in inspect.get_authority_agent_ids(world)
               for event in read_agent(world, agent).get("gameplay_reason_history", ()) if event["reason"] == "AquaticHatch"}
    result["resumed_hatches"] = sorted(hatches)
    if water_forage_shared:
        before = {tuple(row) for row in result["checkpoint_initial_shared_meals"]}
        meals = [row for row in drift_forage_payments(world, "IslandRiverDrift") if tuple(row) not in before]
        if not meals and now < result["checkpoint_loaded_at"] + 60.:
            return False
        if not meals:
            raise RuntimeError("No new shared water forage payments after restoring")
        result["checkpoint_resumed_shared_meals"] = meals
    if not hatches and not water_forage_drawdown:
        raise RuntimeError("No aquatic hatch after resuming the pending reservation")
    return True


def drift_forage_payments(world, patch_id="IslandRiverGravelNearRoots"):
    return [(str(agent), event["time"], event["amount"])
            for agent in inspect.get_authority_agent_ids(world)
            for event in (read_agent(world, agent) or {}).get("gameplay_reason_history", ())
            if event["reason"] == "HabitatPatchEaten" and event.get("resource_id") == patch_id]


def set_shared_forage_drawdown(world, runtime, now):
    river = authored["river"]
    drift, = (patch for patch in runtime.get_editor_property("fauna_habitat_patches")
              if str(patch.get_editor_property("id")) == "IslandRiverDrift")
    main = drift.get_editor_property("center")
    extra, = drift.get_editor_property("forage_access_points")
    habitats = {str(actor.get_editor_property("habitat_id")): actor
                for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
                if str(actor.get_editor_property("region_id")) == river
                and actor.get_editor_property("supports_fauna_swimming")}

    def observe():
        sites = {}
        for name, point in (("main", main), ("extra", extra)):
            column = inspect.inspect_fauna_water(world, river, point, 1.)
            if not column:
                raise RuntimeError(f"Missing water column at shared forage point {name}")
            bounds = column[0]
            sites[name] = {"bottom_cm": bounds.x, "surface_cm": bounds.y,
                           "submerged": bounds.x < point.z < bounds.y}
        clock = u.GameplayStatics.get_game_state(world).get_ecology_summary().get_editor_property("time")
        return {"world_seconds": now, "authority_seconds": clock.get_editor_property("server_time_seconds"),
                "sites": sites}

    trial = result.setdefault("shared_forage_drawdown", {})
    if "before" in trial:
        for name, surface in trial["surfaces_cm"].items():
            habitats[name].set_editor_property("water_surface_z", surface)
        trial["restored"] = observe()
        if trial["restored"]["sites"] != trial["before"]["sites"]:
            raise RuntimeError("Shared forage water levels did not recover after the drawdown")
        return

    trial["before"] = observe()
    if not all(site["submerged"] for site in trial["before"]["sites"].values()):
        raise RuntimeError("Expected both shared forage points to start underwater")
    trial["surfaces_cm"] = {}
    for name, actor in habitats.items():
        bounds = actor.get_editor_property("bounds")
        local = u.MathLibrary.inverse_transform_location(bounds.get_world_transform(), extra)
        if not all(abs(a) <= b for a, b in zip(local.to_tuple(), bounds.get_unscaled_box_extent().to_tuple())):
            continue
        if actor.get_editor_property("water_rain_rise_cm") or actor.get_editor_property("water_level_rise"):
            raise RuntimeError(f"Shared forage drawdown requires a static provider: {name}")
        surface = actor.get_editor_property("water_surface_z")
        if surface > extra.z:
            trial["surfaces_cm"][name] = surface
            actor.set_editor_property("water_surface_z", extra.z - 6.)
    trial["lowered"] = observe()
    if (not trial["surfaces_cm"] or not trial["lowered"]["sites"]["main"]["submerged"]
            or trial["lowered"]["sites"]["extra"]["submerged"]):
        raise RuntimeError("Drawdown must expose only the additional shared forage point")


def sample_shore_rain(world, runtime, now):
    shore = result["saved_mink_shore"]
    river = authored["river"]
    if "shore_rain" not in result:
        habitat, = (actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
                    if str(actor.get_editor_property("habitat_id")) == "IslandLowerRiver05")
        bounds = habitat.get_editor_property("bounds")
        local_bank = u.MathLibrary.inverse_transform_location(bounds.get_world_transform(), u.Vector(*shore["shore_point"]))
        extent = bounds.get_unscaled_box_extent()
        if result["cover_shore_bank"]:
            extent = u.Vector(max(extent.x, abs(local_bank.x) + 35.), max(extent.y, abs(local_bank.y) + 35.), extent.z)
            bounds.set_box_extent(extent, True)
        result["shore_rain_bank_in_volume"] = all(abs(coord) <= limit for coord, limit in zip(local_bank.to_tuple(), extent.to_tuple()))
        if result["survey_flood_exit"]:
            survey_mink_flood_exits(world, shore, habitat.get_editor_property("water_surface_z"))
        if result["high_bank_trial"] is not None:
            add_mink_high_bank_trial(world, runtime, habitat, shore)
        habitat.set_editor_property("water_rain_rise_cm", 24.)
        result["shore_rain"] = []
    entry = u.Vector(*shore["water_entry_point"])
    column = inspect.inspect_fauna_water(world, river, entry, 4.)
    if not column:
        raise RuntimeError("The shore trial lost its water column")
    bottom, surface = column[0].to_tuple()
    observation = {"time": now, "bottom_z": bottom, "surface_z": surface,
                   "bank_above_surface_cm": shore["shore_point"][2] - surface}
    if "high_bank_candidate" in result:
        observation["high_bank_above_surface_cm"] = result["high_bank_candidate"]["bank"][2] - surface
    result["shore_rain"].append(observation)


def sample_nursery_drawdown(world, runtime, now):
    trial = result["nursery_fry" if nursery_fry else "nursery_drawdown"]
    events = trial["events"]
    if (now < 120. or ("restored" in events and not nursery_fry)
            or ("sampled_at" in trial and now - trial["sampled_at"] < .25)):
        return
    trial["sampled_at"] = now
    agent = read_agent(world, 104)
    if not agent or agent["species"] != "CommonCarp":
        return
    history = agent.get("gameplay_reason_history", ())
    inlet_id = "IslandRiverInletPlants"
    if "reservation" not in trial:
        reservation = next((event for event in history if event["reason"] == "BirthAquaticNurseryReserved"
                            and event.get("resource_id") == inlet_id), None)
        if reservation is None:
            return
        trial["reservation"] = reservation
    reservation = trial["reservation"]
    clock = u.GameplayStatics.get_game_state(world).get_ecology_summary().get_editor_property("time")
    authority_now = clock.get_editor_property("server_time_seconds")
    due = reservation["amount"]
    if nursery_fry:
        if "hatch" not in trial:
            hatch = next((event for event in history if event["reason"] == "AquaticHatch"
                          and event["time"] >= due and event["time"] - due < 8.), None)
            if hatch is None:
                return
            child = read_agent(world, int(hatch["related_id"]))
            if not child or child["species"] != "CommonCarp":
                raise RuntimeError("Cannot inspect the newly hatched carp")
            trial["hatch"] = hatch
            trial["hatch_observed_world_seconds"] = now
            species, = (row for row in runtime.get_editor_property("fauna_species")
                        if str(row.get_editor_property("species_id")) == "CommonCarp")
            trial["body_radius_cm"] = species.get_editor_property("body_radius")
        if now - trial["hatch_observed_world_seconds"] > 21.:
            return
    elif authority_now < due - (4. if "lowered" in events else 12.):
        return
    river = authored["river"]
    patches = {str(p.get_editor_property("id")): p.get_editor_property("center")
               for p in runtime.get_editor_property("fauna_habitat_patches")}
    inlet, margin = (patches[f"IslandRiver{name}"] for name in ("InletPlants", "QuietMargin"))

    def observe():
        sites = {}
        for name, center in (("inlet", inlet), ("margin", margin)):
            bounds, _ = inspect.inspect_fauna_water(world, river, center, .5)
            sites[name] = {"bottom_cm": bounds.x, "surface_cm": bounds.y,
                           "submerged": bounds.x < center.z < bounds.y}
        return {"world_seconds": now, "completed_authority_seconds": authority_now,
                "sites": sites}

    habitats = {str(actor.get_editor_property("habitat_id")): actor
                for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
                if str(actor.get_editor_property("region_id")) == river
                and actor.get_editor_property("supports_fauna_swimming")}
    if "lowered" not in events:
        events["before"] = observe()
        if not all(site["submerged"] for site in events["before"]["sites"].values()):
            raise RuntimeError("Expected both nurseries to be submerged before the drawdown")
        trial["original_surface_cm"] = {}
        for name, actor in habitats.items():
            bounds = actor.get_editor_property("bounds")
            local = u.MathLibrary.inverse_transform_location(bounds.get_world_transform(), inlet)
            if not all(abs(a) <= b for a, b in zip(local.to_tuple(), bounds.get_unscaled_box_extent().to_tuple())):
                continue
            if actor.get_editor_property("water_rain_rise_cm") or actor.get_editor_property("water_level_rise"):
                raise RuntimeError(f"Unexpected dynamic water at inlet: {name}")
            trial["original_surface_cm"][name] = actor.get_editor_property("water_surface_z")
            if nursery_fry != "Control":
                actor.set_editor_property("water_surface_z", inlet.z - 8.)
            elif "-EcoIslandNurseryHighShelf" in command.split():
                actor.set_editor_property("water_surface_z", trial["original_surface_cm"][name] + 24.)
        events["lowered"] = observe()
        if "-EcoIslandNurseryDeepShelf" in command.split():
            if nursery_fry != "Drawdown":
                raise RuntimeError("The deeper shelf trial requires a post-hatch drawdown")
            patch_rows = list(runtime.get_editor_property("fauna_habitat_patches"))
            shelf, = (patch for patch in patch_rows if str(patch.get_editor_property("id")) == "IslandRiverSlowShelf")
            center = shelf.get_editor_property("center")
            column = inspect.inspect_fauna_water(world, river, center, 1.)
            if not column or column[0].y - column[0].x < 20. or center.z <= column[0].y:
                raise RuntimeError("Expected an exposed shelf over a persistent water column")
            original_center = list(center.to_tuple())
            deeper = u.Vector(center.x, center.y, (column[0].x + column[0].y) * .5)
            shelf.set_editor_property("center", deeper)
            runtime.set_editor_property("fauna_habitat_patches", patch_rows)
            trial["deeper_shelf"] = {"original_center_cm": original_center,
                                    "trial_center_cm": list(deeper.to_tuple())}
        if (not trial["original_surface_cm"] or events["lowered"]["sites"]["inlet"]["submerged"] != (nursery_fry == "Control")
                or events["lowered"]["sites"]["margin"] != events["before"]["sites"]["margin"]):
            raise RuntimeError("Unexpected nursery water after the trial condition was applied")
    elif "restored" not in events and (not nursery_fry or now >= trial["hatch_observed_world_seconds"] + 8.):
        if not nursery_fry:
            interrupted = next((event for event in history if event["reason"] == "BirthAquaticNurseryInterrupted"
                                and event.get("resource_id") == inlet_id
                                and event["related_id"] == reservation["related_id"]
                                and reservation["time"] <= event["time"] < due), None)
            if not interrupted:
                raise RuntimeError("Authority did not interrupt the selected reservation during drawdown")
            events["interrupted"] = interrupted
        for name, surface in trial["original_surface_cm"].items():
            habitats[name].set_editor_property("water_surface_z", surface)
        if "deeper_shelf" in trial:
            patch_rows = list(runtime.get_editor_property("fauna_habitat_patches"))
            shelf, = (patch for patch in patch_rows if str(patch.get_editor_property("id")) == "IslandRiverSlowShelf")
            shelf.set_editor_property("center", u.Vector(*trial["deeper_shelf"]["original_center_cm"]))
            runtime.set_editor_property("fauna_habitat_patches", patch_rows)
        events["restored"] = observe()
        if events["restored"]["sites"] != events["before"]["sites"]:
            raise RuntimeError("Nursery water did not return to the original levels")
    if nursery_fry:
        record_nursery_fry(world, trial, river, now, authority_now)


def record_nursery_fry(world, trial, river, now, authority_now):
    child = read_agent(world, int(trial["hatch"]["related_id"]))
    sample = {"world_seconds": now, "authority_seconds": authority_now, "present": bool(child)}
    if child:
        xyz = list(map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", child["position"])))
        column = inspect.inspect_fauna_water(world, river, u.Vector(*xyz), .5)
        clearance = max(1., trial["body_radius_cm"] * child["body_scale"] * .65)
        sample.update(position_cm=xyz, clearance_estimate_cm=clearance,
                      hp=child["hp"], energy=child["energy"], water_column_cm=list(column[0].to_tuple()) if column else None,
                      food_patch_index=child["rule_fauna"]["food_patch_index"])
        for event in child.get("gameplay_reason_history", ()):
            if event["reason"] == "HabitatPatchEaten" and event not in trial["payments"]:
                trial["payments"].append(event)
    trial["samples"].append(sample)


def connected_depth_cells(depths, minimum):
    remaining = {cell for cell, depth in depths.items() if depth >= minimum}
    components = []
    while remaining:
        queue = [remaining.pop()]
        for x, y in queue:
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
        components.append(set(queue))
    return components


def stage_water_forage_split(runtime, drift=water_forage_drift, fraction=water_forage_split_fraction):
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    source_id = "IslandRiverGravelInsects"
    if water_forage_small_fish:
        source_id = "IslandRiverDrift" if water_forage_from_drift else "IslandRiverQuietMargin"
    source, = (patch for patch in patches if str(patch.get_editor_property("id")) == source_id)
    roots, = (patch for patch in patches if str(patch.get_editor_property("id")) == "IslandRiverRoots")
    center = roots.get_editor_property("center")
    point = center + u.Vector(230., 0., 12.)
    patch_id = "IslandRiverGravelNearRoots"
    if drift:
        # Founder 103 uses the deep bank beside Drift; Drift itself has other consumers.
        point = u.Vector(92968.58, 41462.64, -4524.10)
    elif water_forage_small_fish:
        point = center + u.Vector(65., 0., 91.)
        patch_id = "IslandRiverDriftForageNearRoots" if water_forage_from_drift else "IslandRiverQuietForageNearRoots"
    copy = source.copy()
    copy.set_editor_property("id", patch_id)
    copy.set_editor_property("center", point)
    copy.set_editor_property("aquatic_nursery", False)
    for field in ("capacity", "regrowth_per_second"):
        original = source.get_editor_property(field)
        source.set_editor_property(field, original * (1. - fraction))
        copy.set_editor_property(field, original * fraction)
    runtime.modify()
    runtime.set_editor_property("fauna_habitat_patches", [*patches, copy])
    return {"patch": patch_id, "source": source_id, "center_cm": list(point.to_tuple()),
            "fraction_reallocated": fraction, "drift_trial": drift}


def save_verified_drift_forage():
    for seed in (20000, 20017):
        report = json.loads((out.parent / f"Island_{seed}_water_drift20" / "IslandFaunaPIE.json").read_bytes())
        log = (out.parent / "IslandAccessBaseline" / f"{seed}_water_drift20.log").read_text(encoding="utf-8")
        trial = report["water_forage_split"]
        if (report["errors"] or not report["water_forage_split_verified"] or report["samples"][-1]["time"] < 720.
                or not trial["drift_trial"] or trial["fraction_reallocated"] != .2
                or not re.search(r"\[PatchMeal\] Patch=IslandRiverGravelNearRoots Species=AriakeCatfish Agent=", log)):
            raise RuntimeError(f"Drift forage was not verified for seed {seed}")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    runtime, = (actor for actor in actors if isinstance(actor, u.EcoCreatureIntegrationSpawner))
    patches = runtime.get_editor_property("fauna_habitat_patches")
    gravel, = (patch for patch in patches if str(patch.get_editor_property("id")) == "IslandRiverGravelInsects")
    if abs(gravel.get_editor_property("capacity") - 11.) > .001 or any(
            str(patch.get_editor_property("id")) == "IslandRiverGravelNearRoots" for patch in patches):
        raise RuntimeError("Expected the original GravelInsects allocation before saving")
    stage_water_forage_split(runtime, drift=True, fraction=.2)
    if not levels.save_current_level():
        raise RuntimeError("Could not save the verified Drift forage")
    u.log("ECO_ISLAND_DRIFT_FORAGE_SAVED")


def sample_water_forage(world, runtime, now):
    river = authored["river"]
    patch_rows = [patch for patch in runtime.get_editor_property("fauna_habitat_patches")
                  if str(patch.get_editor_property("region_id")) == river and patch.get_editor_property("submerged")]
    sites = {str(patch.get_editor_property("id")): patch.get_editor_property("center") for patch in patch_rows}
    profiles = {str(profile.get_editor_property("species_id")): profile
                for profile in runtime.get_editor_property("fauna_species")}
    species = ("AriakeCatfish", "CommonCarp", "UnidentifiedFish")
    pitch = 150.
    x0, y0 = min(p.x for p in sites.values()) - 600., min(p.y for p in sites.values()) - 600.
    nx = math.ceil((max(p.x for p in sites.values()) + 600. - x0) / pitch)
    ny = math.ceil((max(p.y for p in sites.values()) + 600. - y0) / pitch)
    z = sum(point.z for point in sites.values()) / len(sites)
    samples = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            column = inspect.inspect_fauna_water(world, river, u.Vector(x0 + i * pitch, y0 + j * pitch, z), .5)
            if column:
                samples[i, j] = column[0].y - column[0].x
    at_site = {name: inspect.inspect_fauna_water(world, river, point, .5) for name, point in sites.items()}
    geometry = {}
    for kind in species:
        profile = profiles[kind]
        reach = profile.get_editor_property("sight_range")
        day_range = reach * (.25 + .75 * profile.get_editor_property("day_activity"))
        night_range = reach * (.25 + .75 * profile.get_editor_property("night_activity"))
        allowed = [str(row.get_editor_property("id")) for row in patch_rows
                   if kind in set(map(str, row.get_editor_property("consumers")))]
        geometry[kind] = {}
        for scale in (.75, 1.):
            clearance = max(1., profile.get_editor_property("body_radius") * scale * .65)
            components = connected_depth_cells(samples, 2. * clearance)
            component_by_cell = {cell: index for index, cells in enumerate(components) for cell in cells}
            site_component = {}
            for name in allowed:
                point = sites[name]
                if not at_site[name] or at_site[name][0].y - at_site[name][0].x < 2. * clearance:
                    continue
                cell = (round((point.x - x0) / pitch), round((point.y - y0) / pitch))
                if cell in component_by_cell:
                    site_component[name] = component_by_cell[cell]
            pairs = {}
            for left, right in combinations(allowed, 2):
                a, b = sites[left], sites[right]
                distance = (b - a).length()
                spans = max(1, math.ceil(distance / 50.))
                missing = sum(not inspect.inspect_fauna_water(world, river, a + (b - a) * (i / spans), clearance)
                              for i in range(spans + 1))
                pairs[f"{left}:{right}"] = {
                    "distance_cm": distance, "within_max_sight_range": distance <= reach,
                    "within_nominal_day_food_range": distance <= day_range,
                    "within_nominal_night_food_range": distance <= night_range,
                    "connected_depth_grid": left in site_component and site_component[left] == site_component.get(right),
                    "straight_missing_water_samples": missing, "straight_samples": spans + 1,
                }
            geometry[kind][str(scale)] = {"clearance_cm": clearance, "pairs": pairs,
                                         "nominal_food_range_cm": {"day": day_range, "night": night_range}}
    survey = {"world_seconds": now, "grid_cm": pitch, "wet_cells": len(samples), "species": geometry,
              "site_water_cm": {name: list(value[0].to_tuple()) if value else None for name, value in at_site.items()}}
    if capture_water_forage_grid:
        survey["depth_grid"] = {
            "origin_cm": [x0, y0],
            "sites_cm": {name: list(point.to_tuple()) for name, point in sites.items()},
            "samples": [[x, y, depth] for (x, y), depth in samples.items()],
        }
    if survey_water_detour:
        clearance = geometry["UnidentifiedFish"]["1.0"]["clearance_cm"]
        survey["detour_edges"] = probe_water_detour(world, river, samples, (x0, y0), pitch, z, clearance,
                                                     sites["IslandRiverDrift"], sites["IslandRiverSlowShelf"])
    return survey


def probe_water_detour(world, river, depths, origin, pitch, probe_z, clearance, start, goal):
    module_path = str(Path(u.Paths.project_dir()).resolve() / "Tools" / "EcoVegetationEval")
    sys.path.insert(0, module_path)
    try:
        from island_water_reference_world import GRID_MOVES, WaterGridWorld
    finally:
        sys.path.pop(0)
    start_cell, goal_cell = [tuple(round((value - base) / pitch) for value, base in
                                   zip((site.x, site.y), origin)) for site in (start, goal)]
    xy_world = WaterGridWorld(depths, start_cell, clearance, {}, 0., 1.)
    route = xy_world.route_to(goal_cell)
    if not route:
        raise RuntimeError("Expected a depth-grid route before querying the swept water edges")
    edges = []
    joins = []
    static = [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1]
    spans = math.ceil(pitch / 25.)

    def clearance_sweep(a, b):
        ignored = []
        while hit := u.SystemLibrary.sphere_trace_single_for_objects(
                world, a, b, max(.5, clearance - .2), static, False, ignored, u.DrawDebugTrace.NONE, True):
            actor = hit.to_tuple()[9]
            if not actor or not isinstance(actor, u.WaterBody) or actor in ignored:
                return False
            ignored.append(actor)
        return True

    for action in route:
        x, y = xy_world.cell
        dx, dy = GRID_MOVES[action]
        positions = [u.Vector(origin[0] + (x + dx * i / spans) * pitch,
                              origin[1] + (y + dy * i / spans) * pitch, probe_z) for i in range(spans + 1)]
        columns = [inspect.inspect_fauna_water(world, river, point, clearance) for point in positions]
        row = {"from": [x, y], "to": [x + dx, y + dy], "samples": len(columns),
               "missing_water": sum(not column for column in columns)}
        if row["missing_water"]:
            row["result"] = "missing_water"
        else:
            bottom = max(column[0].x for column in columns) + clearance
            surface = min(column[0].y for column in columns) - clearance
            row["center_bounds_cm"] = [bottom, surface]
            if bottom > surface:
                row["result"] = "no_common_depth"
            else:
                a, b = positions[0], positions[-1]
                a.z = b.z = (bottom + surface) * .5
                row["result"] = "clear" if clearance_sweep(a, b) else "blocked_sweep"
                row["sweep_z_cm"] = a.z
                if edges and edges[-1]["result"] == "clear" and row["result"] == "clear":
                    previous_z = edges[-1]["sweep_z_cm"]
                    low, high = columns[0][0].to_tuple()
                    arrival = u.Vector(a.x, a.y, previous_z)
                    in_column = low + clearance <= min(previous_z, a.z) <= max(previous_z, a.z) <= high - clearance
                    joins.append({"cell": [x, y], "from_z_cm": previous_z, "to_z_cm": a.z,
                                  "water_column_cm": [low, high],
                                  "clear": in_column and clearance_sweep(arrival, a)})
        edges.append(row)
        if xy_world.step(action)["outcome"] != "moved":
            raise RuntimeError("Detour did not follow the same sampled depth grid")
    return {"clearance_cm": clearance, "edges": edges, "joins": joins}


def sample_nursery_depth(world, runtime, now):
    species, = (row for row in runtime.get_editor_property("fauna_species")
                if str(row.get_editor_property("species_id")) == "CommonCarp")
    radius = species.get_editor_property("body_radius")
    minima = {name: 2. * max(1., radius * scale * .65) for name, scale in (("newly_hatched", .75), ("adult", 1.))}
    step, half = 40., 15
    sites = {}
    patches = runtime.get_editor_property("fauna_habitat_patches")
    for patch in patches:
        name = str(patch.get_editor_property("id"))
        if name not in {"IslandRiverInletPlants", "IslandRiverQuietMargin"}:
            continue
        center = patch.get_editor_property("center")
        depths = {}
        center_water = None
        for x in range(-half, half + 1):
            for y in range(-half, half + 1):
                water = inspect.inspect_fauna_water(world, authored["river"], center + u.Vector(x * step, y * step, 0.), .5)
                if not water:
                    continue
                bottom, surface = water[0].to_tuple()
                depths[(x, y)] = surface - bottom
                if (x, y) == (0, 0):
                    center_water = {"bottom_z_cm": bottom, "surface_z_cm": surface, "center_submerged": bottom < center.z < surface}
        cohorts = {}
        for name_class, minimum in minima.items():
            components = connected_depth_cells(depths, minimum)
            origin = next((component for component in components if (0, 0) in component), set())
            cohorts[name_class] = {
                "minimum_depth_cm": minimum,
                "component_areas_m2": sorted((round(len(group) * (step / 100.) ** 2, 2) for group in components), reverse=True),
                "center_component_area_m2": round(len(origin) * (step / 100.) ** 2, 2),
                "center_component_touches_survey_edge": any(abs(x) == half or abs(y) == half for x, y in origin),
            }
        sites[name] = {"center_cm": list(center.to_tuple()), "water_at_center": center_water, "cohorts": cohorts}
    if len(sites) != 2:
        raise RuntimeError("Expected both saved carp nursery sites")
    return {"world_seconds": now, "grid_cm": step, "half_width_cm": step * half, "sites": sites}


def add_mink_high_bank_trial(world, runtime, habitat, shore):
    survey = out.parent / "IslandAccess_20000_saved_feeding_saved_mink_saved_perch_rain_bank_survey" / "IslandFaunaPIE.json"
    data = json.loads(survey.read_text(encoding="utf-8"))
    candidate = data["flood_exit_survey"]["candidates"][result["high_bank_trial"]]
    bank, entry = (u.Vector(*candidate[key]) for key in ("bank", "entry"))
    bounds = habitat.get_editor_property("bounds")
    extent = bounds.get_unscaled_box_extent()
    for point in (bank, entry):
        local = u.MathLibrary.inverse_transform_location(bounds.get_world_transform(), point)
        extent = u.Vector(max(extent.x, abs(local.x) + 35.), max(extent.y, abs(local.y) + 35.), extent.z)
    bounds.set_box_extent(extent, True)
    food = u.Vector(*shore["center"])
    for i in range(21):
        if not inspect.inspect_fauna_water(world, authored["river"], entry + (food - entry) * (i / 20.), 6.):
            raise RuntimeError(f"High bank approach lacks a continuous water column at sample {i}")
    patches = [p.copy() for p in runtime.get_editor_property("fauna_habitat_patches")]
    patch, = (p for p in patches if str(p.get_editor_property("id")) == "IslandRiverRootsShore")
    patch.set_editor_property("shore_point", bank)
    patch.set_editor_property("water_entry_point", entry)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    result["high_bank_candidate"] = candidate


def survey_mink_founder_shore(world, runtime):
    agent = read_agent(world, 111)
    if not agent or agent["species"] != "Mink" or agent["region"] != authored["river"]:
        raise RuntimeError("Second mink founder was unavailable in the saved reach")
    start = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))
    patches = runtime.get_editor_property("fauna_habitat_patches")
    patch, = (p for p in patches if str(p.get_editor_property("id")) == "IslandRiverRootsShore")
    entry = patch.get_editor_property("water_entry_point")
    column = inspect.inspect_fauna_water(world, authored["river"], entry, 4.)
    if not column:
        raise RuntimeError("Existing mink shore has no authority water column")
    # Keep the first survey within the current 850 cm search distance.
    report = survey_mink_shore_geometry(world, start, column[0].y, 850.)
    report["founder_id"] = 111
    report["survey_origin_cm"] = list(start.to_tuple())
    report["reference_water_point_cm"] = list(entry.to_tuple())
    for candidate in report["candidates"]:
        point = u.Vector(*candidate["entry"])
        water = inspect.inspect_fauna_water(world, authored["river"], point, 4.)
        candidate["inside_authority_water"] = bool(water)
        if water:
            candidate["local_water_surface_z"] = water[0].y
    if survey_local_mink_water:
        report["local_authority_water"] = survey_mink_local_water(world, start, patches)
    result["second_mink_shore_survey"] = report


def apply_second_mink_shore_trial(world, runtime):
    evidence = out.parent / "Island_20000_mink_ground" / "IslandFaunaPIE.json"
    pairs = json.loads(evidence.read_bytes())["second_mink_shore_survey"]["local_authority_water"]["local_shore_pairs"]
    candidate = pairs["ground_reachable_candidates"][second_mink_trial]
    bank = u.Vector(*candidate["bank_cm"])
    entry = u.Vector(*candidate["entry_cm"])
    river = authored["river"]
    direction = u.Vector(entry.x - bank.x, entry.y - bank.y, 0.)
    direction = direction / direction.length()
    food = None
    for distance in range(10, 151, 10):
        point = entry + direction * distance
        water = inspect.inspect_fauna_water(world, river, point, 6.)
        if not water:
            break
        bottom, surface = water[0].to_tuple()
        if surface - bottom >= 24.:
            food = u.Vector(point.x, point.y, (bottom + surface) * .5)
    if food is None:
        raise RuntimeError("Selected mink entry has no connected nearby food point")
    patches = [patch.copy() for patch in runtime.get_editor_property("fauna_habitat_patches")]
    shore, = (patch for patch in patches if str(patch.get_editor_property("id")) == "IslandRiverRootsShore")
    donor = next(patch for patch in patches if str(patch.get_editor_property("id")) == "IslandRiverRoots") if second_mink_deep_budget else shore
    saved = next((patch for patch in patches if str(patch.get_editor_property("id")) == "IslandRiverSecondMinkShore"), None)
    if saved is not None:
        # Undo the saved split in this PIE instance before applying the historical trial layout.
        roots, = (patch for patch in patches if str(patch.get_editor_property("id")) == "IslandRiverRoots")
        for name in ("capacity", "regrowth_per_second"):
            roots.set_editor_property(name, roots.get_editor_property(name) + saved.get_editor_property(name))
        patches = [patch for patch in patches if str(patch.get_editor_property("id")) != "IslandRiverSecondMinkShore"]
        for actor in u.GameplayStatics.get_all_actors_of_class(world, u.StaticMeshActor):
            if actor.get_actor_label() == "JYU_LowerRiver_DryBankShelf":
                actor.set_actor_enable_collision(False)
    share = .15 if second_mink_deep_budget else .25
    local = shore.copy()
    local.set_editor_property("id", "IslandRiverSecondMinkShore")
    local.set_editor_property("center", food)
    local.set_editor_property("shore_point", bank)
    local.set_editor_property("water_entry_point", entry)
    budget = {}
    for name in ("capacity", "regrowth_per_second"):
        total = donor.get_editor_property(name)
        moved = total * share
        donor.set_editor_property(name, total - moved)
        local.set_editor_property(name, moved)
        budget[name] = {"before": total, "existing": total - moved, "local": moved}
    runtime.set_editor_property("fauna_habitat_patches", patches + [local])
    authored["water_samples"]["SecondMinkShore"] = list(food.to_tuple())
    result["second_mink_trial"] = {"candidate": candidate, "food_cm": list(food.to_tuple()), "budget": budget,
                                   "donor_patch": str(donor.get_editor_property("id"))}


def sample_second_mink_flood(world, runtime, now):
    if now < 50.:
        return
    agent = read_agent(world, 111)
    trial = result.setdefault("second_mink_flood", {"samples": []})
    if not agent or not agent.get("rule_fauna"):
        return
    history = agent.get("gameplay_reason_history", ())
    if "rise" not in trial and not any(event["reason"] == "SwimEnter" for event in history):
        return
    if "restored" in trial and now - trial["restored"]["world_seconds"] > 20.:
        return
    points = result["second_mink_trial"]["candidate"]
    bank = u.Vector(*points["bank_cm"])
    entry = u.Vector(*points["entry_cm"])
    river = authored["river"]
    column = inspect.inspect_fauna_water(world, river, entry, 6.)
    if not column:
        raise RuntimeError("Second mink flood lost the entry column")
    if "rise" not in trial or ("restored" not in trial and now - trial["rise"]["world_seconds"] >= 35.):
        raising = "rise" not in trial
        habitats = {str(actor.get_editor_property("habitat_id")): actor
                    for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
                    if str(actor.get_editor_property("region_id")) == river
                    and actor.get_editor_property("supports_fauna_swimming")}
        if raising:
            before = column[0].y
            original = {}
            trial["provider_bank_membership"] = {}
            for name, actor in habitats.items():
                bounds = actor.get_editor_property("bounds")
                transform = bounds.get_world_transform()
                extent = bounds.get_unscaled_box_extent()
                local = u.MathLibrary.inverse_transform_location(transform, entry)
                if not all(abs(a) <= b for a, b in zip(local.to_tuple(), extent.to_tuple())):
                    continue
                if actor.get_editor_property("water_rain_rise_cm") or actor.get_editor_property("water_level_rise"):
                    raise RuntimeError(f"Second mink flood requires static water at {name}")
                original[name] = actor.get_editor_property("water_surface_z")
                local_bank = u.MathLibrary.inverse_transform_location(transform, bank)
                contained = all(abs(a) <= b for a, b in zip(local_bank.to_tuple(), extent.to_tuple()))
                trial["provider_bank_membership"][name] = contained
                if second_mink_flood_cover_bank and not contained:
                    trial.setdefault("original_bounds_extent_cm", {})[name] = list(extent.to_tuple())
                    bounds.set_box_extent(u.Vector(max(extent.x, abs(local_bank.x) + 50.),
                                                   max(extent.y, abs(local_bank.y) + 50.),
                                                   max(extent.z, abs(local_bank.z) + 50.)), True)
            if not original:
                raise RuntimeError("Could not locate the second mink entry water provider")
            trial["original_surface_cm"] = original
            for name, surface in original.items():
                habitats[name].set_editor_property("water_surface_z", surface + 24.)
        else:
            before = trial["rise"]["original_surface_cm"]
            for name, surface in trial["original_surface_cm"].items():
                habitats[name].set_editor_property("water_surface_z", surface)
            for name, extent in trial.get("original_bounds_extent_cm", {}).items():
                habitats[name].get_editor_property("bounds").set_box_extent(u.Vector(*extent), True)
        column = inspect.inspect_fauna_water(world, river, entry, 6.)
        expected = before + 24. if raising else before
        if not column or abs(column[0].y - expected) > .02:
            raise RuntimeError("Second mink entry did not receive the requested water level")
        label = "rise" if raising else "restored"
        trial[label] = {"world_seconds": now, "surface_cm": column[0].y,
                        "original_surface_cm": before, "bank_above_surface_cm": bank.z - column[0].y}
        if raising and second_mink_flood_survey:
            trial["alternate_shore"] = survey_second_mink_high_water(world, river, entry, column[0].y)
        if raising and second_mink_flood_connector:
            survey_second_mink_connector(world, trial, habitats, river)
        if raising and second_mink_flood_platform:
            install_second_mink_flood_platform(world, runtime, trial, bank, entry, column[0].y)
            if second_mink_exit_cover:
                food = u.Vector(*result["second_mink_trial"]["food_cm"])
                center = food + (entry - food) * .65
                cover = u.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(
                    world, u.StaticMeshActor, u.Transform(location=center))
                if cover is None:
                    raise RuntimeError("Could not place mink exit sight cover")
                mesh = cover.static_mesh_component
                mesh.set_mobility(u.ComponentMobility.MOVABLE)
                mesh.set_static_mesh(u.load_asset("/Engine/BasicShapes/Cube"))
                mesh.set_collision_profile_name("EcoFaunaSightCoverQuery")
                cover.set_actor_scale3d(u.Vector(.48, .48, .48))
                cover.set_editor_property("tags", ["JYU.MinkExitCoverAudit"])
                trial["exit_sight_cover_cm"] = list(center.to_tuple())
        if not raising and second_mink_remove_exit_cover:
            cover, = u.GameplayStatics.get_all_actors_with_tag(world, "JYU.MinkExitCoverAudit")
            cover.set_actor_enable_collision(False)
            trial["exit_cover_removed_world_seconds"] = now
    details = agent["rule_fauna"]
    if second_mink_exit_cover and "restored" not in trial and details["swimming"] and details["stamina"] < .95:
        previous = trial["samples"][-1] if trial["samples"] else None
        if previous and previous["position"] == agent["position"] and "exit_inputs" not in trial:
            point = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))
            frame = inspect.inspect_fauna_water(world, river, point, 1.)
            if frame:
                exits = []
                for patch in runtime.get_editor_property("fauna_habitat_patches"):
                    if (not patch.get_editor_property("has_shore_entry")
                            or str(patch.get_editor_property("region_id")) != river
                            or "Mink" not in map(str, patch.get_editor_property("consumers"))):
                        continue
                    mouth = patch.get_editor_property("water_entry_point")
                    shore = patch.get_editor_property("shore_point")
                    water = inspect.inspect_fauna_water(world, river, mouth, 1.)
                    exits.append({"id": str(patch.get_editor_property("id")), "entry_cm": list(mouth.to_tuple()),
                                  "bank_cm": list(shore.to_tuple()), "column_cm": [water[0].x, water[0].y] if water else None})
                trial["exit_inputs"] = {
                    "position_cm": list(point.to_tuple()), "current_cm_s": list(frame[1].to_tuple()),
                    "stamina": details["stamina"], "exits": exits, "world_seconds": now,
                }
    sample = {"world_seconds": now, "position": agent["position"], "hp": agent["hp"],
                             "energy": agent["energy"], "stamina": details["stamina"],
                             "swimming": details["swimming"], "shore_phase": details["shore_phase"],
                             "goal": details["goal"]}
    if second_mink_saved_flood and details["swimming"] and "restored" not in trial:
        position = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))
        water = inspect.inspect_fauna_water(world, river, position, 1.)
        if water:
            sample["water_column_cm"] = [water[0].x, water[0].y]
            sample["current_cm_s"] = list(water[1].to_tuple())
    trial["samples"].append(sample)
    if second_mink_flood_platform and "restored" not in trial and details["swimming"]:
        trace_platform_approach(world, trial, agent, entry, now)
    if second_mink_flood_platform and "restored" not in trial and not details["swimming"] and "platform_exit" not in trial:
        point = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))
        platform = u.Vector(*trial["platform_cm"])
        if (point - platform).length() <= 35.:
            trial["platform_exit"] = {"world_seconds": now, "position_cm": list(point.to_tuple()),
                                      "stamina": details["stamina"]}
            set_camera(world, platform + u.Vector(170., -225., 120.), platform)
            capture(world, "IslandFauna_MinkFloodPlatform")
    if second_mink_flood_ramp and "platform_exit" in trial and "dry_ground_arrival" not in trial and not details["swimming"]:
        record_second_mink_dry_arrival(world, trial, agent, now)
    if (second_mink_saved_flood and "dry_ground_arrival" not in trial and not details["swimming"]
            and any(event["reason"] == "SwimDryBankReached" and event["time"] >= trial["rise"]["world_seconds"] - .6
                    for event in history)):
        trial["ramp"] = result["second_mink_saved_ramp"]
        record_second_mink_dry_arrival(world, trial, agent, now)


def install_second_mink_flood_platform(world, runtime, trial, bank, entry, surface):
    geometry = u.EcoCreatureAnimationBuilder
    platform = entry + (bank - entry) * .8
    platform.z = surface + 10.
    dry_bank = None
    if second_mink_flood_ramp:
        dry_bank = install_second_mink_ramp(world, trial, platform, surface)
    else:
        spawn_mink_walk_surface(world, platform, u.Rotator(), u.Vector(.55, .55, .14))
    projected = geometry.project_placement_point(world, platform)
    if projected is None or (projected - platform).length() > 1. or (projected - entry).length() > 130.:
        raise RuntimeError("PIE-only platform failed landing projection or transition span")
    patches = [p.copy() for p in runtime.get_editor_property("fauna_habitat_patches")]
    patch, = (p for p in patches if str(p.get_editor_property("id")) == "IslandRiverSecondMinkShore")
    patch.set_editor_property("shore_point", projected)
    if second_mink_dry_bank:
        patch.set_editor_property("dry_bank_point", dry_bank)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    trial["platform_cm"] = list(projected.to_tuple())


def spawn_mink_walk_surface(world, top, rotation, scale, authored_actor=False):
    geometry = u.EcoCreatureAnimationBuilder
    normal = u.MathLibrary.get_up_vector(rotation)
    location = top - normal * (scale.z * 50.)
    if authored_actor:
        actors = u.get_editor_subsystem(u.EditorActorSubsystem)
        plate = actors.spawn_actor_from_class(u.StaticMeshActor, location, rotation)
        plate.set_actor_label("JYU_LowerRiver_DryBankShelf")
        plate.set_editor_property("is_spatially_loaded", False)
    else:
        plate = geometry.spawn_visual_audit_actor(world, u.StaticMeshActor,
                                                  u.Transform(location=location, rotation=rotation))
    if plate is None:
        raise RuntimeError("Could not spawn the PIE-only mink landing surface")
    mesh = plate.static_mesh_component
    mesh.set_mobility(u.ComponentMobility.MOVABLE)
    mesh.set_static_mesh(u.load_asset("/Engine/BasicShapes/Cube"))
    mesh.set_collision_profile_name("BlockAll")
    plate.set_actor_scale3d(scale)
    if authored_actor:
        mesh.set_material(0, u.load_asset("/Game/JYU/Materials/M_JYU_Surface_Wet"))
        mesh.set_mobility(u.ComponentMobility.STATIC)
    return plate


def install_second_mink_ramp(world, trial, platform, surface):
    home = u.Vector(*result["second_mink_trial"]["near_start_cm"])
    heading = math.atan2(home.y - platform.y, home.x - platform.x)
    candidates = []
    for offset in (0, -15, 15, -30, 30, -45, 45, -60, 60, -90, 90, -120, 120, -150, 150, 180):
        angle = heading + math.radians(offset)
        direction = u.Vector(math.cos(angle), math.sin(angle), 0.)
        for distance in range(100, 1201, 20):
            point = platform + direction * distance
            floor = mink_landscape_z(world, point)
            if floor is None or floor < surface + 8. or abs(floor - platform.z) > distance * .25:
                continue
            onward = point + direction * 50.
            onward_floor = mink_landscape_z(world, onward)
            if onward_floor is None or onward_floor < surface + 5. or abs(onward_floor - floor) > 12.:
                continue
            candidates.append((distance + abs(offset) * 3., direction, u.Vector(point.x, point.y, floor),
                               u.Vector(onward.x, onward.y, onward_floor), offset))
            break
    if not candidates:
        raise RuntimeError("No dry Landscape endpoint for the PIE mink ramp")
    _, direction, endpoint, dry_bank, offset = min(candidates, key=lambda row: row[0])
    base = platform - direction * 20.
    rotation = u.MathLibrary.find_look_at_rotation(base, endpoint)
    span = (endpoint - base).length()
    width = 400. if second_mink_wide_ramp else 140.
    spawn_mink_walk_surface(world, (base + endpoint) * .5, rotation, u.Vector(span / 100., width / 100., .14))
    trial["ramp"] = {"base_cm": list(base.to_tuple()), "end_cm": list(endpoint.to_tuple()),
                     "direction": list(direction.to_tuple()), "width_cm": width, "span_cm": span,
                     "heading_offset_degrees": offset, "candidate_count": len(candidates)}
    if second_mink_dry_bank:
        trial["ramp"]["dry_bank_cm"] = list(dry_bank.to_tuple())
    return dry_bank


def record_second_mink_dry_arrival(world, trial, agent, now):
    ramp = trial["ramp"]
    end = u.Vector(*ramp["end_cm"])
    point = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))
    direction = u.Vector(*ramp["direction"])
    if (point.x - end.x) * direction.x + (point.y - end.y) * direction.y <= 15.:
        return
    floor = mink_landscape_z(world, point)
    if floor is None or abs(point.z - floor) > 2. or floor < trial["rise"]["surface_cm"] + 5.:
        return
    trial["dry_ground_arrival"] = {"world_seconds": now, "position_cm": list(point.to_tuple()),
                                  "landscape_z_cm": floor, "before_restore": "restored" not in trial}
    set_camera(world, point + u.Vector(180., -230., 130.), point)
    capture(world, "IslandFauna_MinkDryGround")


def trace_platform_approach(world, trial, agent, entry, now):
    rows = trial.setdefault("platform_approach", [])
    if rows and now - rows[-1]["world_seconds"] < 2.:
        return
    position = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))
    water = inspect.inspect_fauna_water(world, authored["river"], entry, 6.)
    if not water:
        return
    bottom, surface = water[0].to_tuple()
    target = u.Vector(entry.x, entry.y, min(surface - 6., max(bottom + 6., entry.z)))
    hit = u.SystemLibrary.line_trace_single_for_objects(
        world, position, target, [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True)
    actor = hit.to_tuple()[9] if hit else None
    rows.append({"world_seconds": now, "distance_to_entry_cm": (position - target).length(),
                 "static_hit_class": actor.get_class().get_name() if actor else None,
                 "clear_audit_sight": u.EcoCreatureAnimationBuilder.has_fauna_audit_sight(world, position, target)})


def survey_second_mink_connector(world, trial, habitats, river):
    evidence = out.parent / "Island_20000_mink_flood_span" / "IslandFaunaPIE.json"
    gap = json.loads(evidence.read_bytes())["second_mink_flood"]["alternate_shore"]["closest_transition_gap"]
    bank, entry = (u.Vector(*gap[key]) for key in ("bank_cm", "entry_cm"))
    name, = trial["original_surface_cm"]
    bounds = habitats[name].get_editor_property("bounds")
    extent = bounds.get_unscaled_box_extent()
    local_bank = u.MathLibrary.inverse_transform_location(bounds.get_world_transform(), bank)
    trial["connector"] = {"before": sample_mink_connector_line(world, river, entry, bank)}
    bounds.set_box_extent(u.Vector(max(extent.x, abs(local_bank.x) + 50.),
                                   max(extent.y, abs(local_bank.y) + 50.),
                                   max(extent.z, abs(local_bank.z) + 50.)), True)
    try:
        trial["connector"]["extended"] = sample_mink_connector_line(world, river, entry, bank)
    finally:
        bounds.set_box_extent(extent, True)
    delta = bank - entry
    side = u.Vector(-delta.y, delta.x, 0.)
    side = side / side.length()
    trial["connector"]["parallel_lines"] = [
        {"offset_cm": offset,
         "samples": sample_mink_connector_line(world, river, entry + side * offset, bank + side * offset)}
        for offset in (-80., -40., 40., 80.)
    ]


def sample_mink_connector_line(world, river, entry, bank):
    distance = math.hypot(entry.x - bank.x, entry.y - bank.y)
    steps = max(1, math.ceil(distance / 10.))
    rows = []
    for i in range(steps + 1):
        fraction = i / steps
        point = entry + (bank - entry) * fraction
        water = inspect.inspect_fauna_water(world, river, point, .5)
        rows.append({"distance_cm": distance * fraction, "position_cm": list(point.to_tuple()),
                     "water_column_cm": list(water[0].to_tuple()) if water else None,
                     "landscape_z_cm": mink_landscape_z(world, point)})
    return rows


def mink_landscape_z(world, point):
    ignored = []
    while hit := u.SystemLibrary.line_trace_single_for_objects(
            world, point + u.Vector(0., 0., 600.), point - u.Vector(0., 0., 800.),
            [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, ignored, u.DrawDebugTrace.NONE, True):
        data = hit.to_tuple()
        if data[10] and "Landscape" in data[10].get_class().get_name():
            return data[5].z
        actor = data[9]
        if actor is None or actor in ignored:
            break
        ignored.append(actor)
    return None


def survey_second_mink_high_water(world, river, origin, surface):
    geometry = u.EcoCreatureAnimationBuilder
    step = 40.
    radius = 2000.
    half = math.floor(radius / step)
    columns = {}
    dry = {}
    for x in range(-half, half + 1):
        for y in range(-half, half + 1):
            if math.hypot(x, y) * step > radius:
                continue
            point = origin + u.Vector(x * step, y * step, 0.)
            water = inspect.inspect_fauna_water(world, river, point, 6.)
            if water:
                bottom, local_surface = water[0].to_tuple()
                if local_surface - bottom >= 20.:
                    columns[x, y] = u.Vector(point.x, point.y, local_surface - 9.)
            ground = geometry.project_placement_point(world, point)
            if ground is not None and ground.z >= surface + 5.:
                dry[x, y] = ground

    pairs = []
    closest_gap = None
    for (x, y), bank in dry.items():
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                entry = columns.get((x + dx, y + dy))
                if entry is None:
                    continue
                span = (entry - bank).length()
                if span <= 130.:
                    pairs.append(((entry - origin).length(), span, bank, entry))
    wet_xyz = [(point.x, point.y, point.z, point) for point in columns.values()]
    best_gap_sq = math.inf
    for bank in dry.values():
        for x, y, z, entry in wet_xyz:
            horizontal_sq = (x - bank.x) ** 2 + (y - bank.y) ** 2
            if horizontal_sq >= best_gap_sq:
                continue
            gap_sq = horizontal_sq + (z - bank.z) ** 2
            if gap_sq < best_gap_sq:
                best_gap_sq = gap_sq
                closest_gap = (bank, entry)
    pairs.sort(key=lambda pair: pair[:2])
    connected = []
    nearest_pair = None
    for distance, span, bank, entry in pairs:
        if nearest_pair is None:
            nearest_pair = {"bank_cm": list(bank.to_tuple()), "entry_cm": list(entry.to_tuple()),
                            "water_distance_cm": distance, "transition_span_cm": span}
        count = max(1, math.ceil(distance / 10.))
        if any(not inspect.inspect_fauna_water(world, river, origin + (entry - origin) * (i / count), 6.)
               for i in range(count + 1)):
            continue
        connected.append({"bank_cm": list(bank.to_tuple()), "entry_cm": list(entry.to_tuple()),
                          "water_distance_cm": distance, "transition_span_cm": span,
                          "bank_above_origin_surface_cm": bank.z - surface})
    return {"stride_cm": step, "radius_cm": radius, "water_points": len(columns), "dry_points": len(dry),
            "pair_count": len(pairs), "nearest_pair": nearest_pair, "water_connected_count": len(connected),
            "closest_transition_gap": ({"span_cm": math.sqrt(best_gap_sq), "bank_cm": list(closest_gap[0].to_tuple()),
                                        "entry_cm": list(closest_gap[1].to_tuple())} if closest_gap else None),
            "candidates": connected[:20]}


def survey_mink_local_water(world, start, patches):
    river = authored["river"]
    stride = 60.
    samples = []
    water_count = 0
    scanned_count = 0
    nearest = None
    edge_columns = []
    for x in range(-50, 51):
        for y in range(-50, 51):
            distance = math.hypot(x, y) * stride
            if distance > 3000.:
                continue
            scanned_count += 1
            point = start + u.Vector(x * stride, y * stride, 0.)
            water = inspect.inspect_fauna_water(world, river, point, 6.)
            if not water:
                continue
            bottom, surface = water[0].to_tuple()
            water_count += 1
            row = {"xy_cm": list(point.to_tuple()[:2]), "distance_cm": distance,
                   "bottom_cm": bottom, "surface_cm": surface}
            if nearest is None or distance < nearest["distance_cm"]:
                nearest = row
            if distance <= 850.:
                samples.append(row)
            if distance <= 980. and surface - bottom >= 16.:
                edge_columns.append(row)
    food = []
    for patch in patches:
        if str(patch.get_editor_property("region_id")) != river or "Mink" not in map(str, patch.get_editor_property("consumers")):
            continue
        point = patch.get_editor_property("center")
        food.append({"id": str(patch.get_editor_property("id")),
                     "distance_cm": math.hypot(point.x - start.x, point.y - start.y),
                     "has_shore_entry": patch.get_editor_property("has_shore_entry")})
    approach = []
    if nearest:
        endpoint = u.Vector(*nearest["xy_cm"], start.z)
        steps = math.ceil(nearest["distance_cm"] / 10.)
        for step in range(steps + 1):
            fraction = step / steps if steps else 0.
            point = start + (endpoint - start) * fraction
            water = inspect.inspect_fauna_water(world, river, point, 6.)
            ground = u.EcoCreatureAnimationBuilder.project_placement_point(world, point)
            approach.append({"distance_cm": nearest["distance_cm"] * fraction,
                             "ground_z_cm": ground.z if ground is not None else None,
                             "water_column_cm": list(water[0].to_tuple()) if water else None})
    return {"stride_cm": stride, "radius_cm": 3000., "scanned_count": scanned_count, "valid_water_count": water_count,
            "nearest_column": nearest, "columns_inside_sight_range": samples, "authored_food_patches": food,
            "approach_to_nearest_column": approach,
            "local_shore_pairs": survey_local_mink_shore_pairs(world, start, edge_columns)}


def survey_local_mink_shore_pairs(world, start, columns):
    # The validated upstream bank is still dry with 24 cm of rain rise.
    candidates = []
    for column in columns:
        surface = column["surface_cm"]
        entry = u.Vector(*column["xy_cm"], surface - 8.)
        for x in range(-4, 5):
            for y in range(-4, 5):
                offset = u.Vector(x * 30., y * 30., 0.)
                hint = entry + offset
                if math.hypot(hint.x - start.x, hint.y - start.y) > 850.:
                    continue
                bank = u.EcoCreatureAnimationBuilder.project_placement_point(world, hint)
                if bank is None:
                    continue
                span = (bank - entry).length()
                if span > 130. or bank.z <= surface:
                    continue
                candidates.append({"bank_cm": list(bank.to_tuple()), "entry_cm": list(entry.to_tuple()),
                                   "span_cm": span, "bank_above_high_water_cm": bank.z - surface - 24.,
                                   "bank_distance_cm": math.hypot(bank.x - start.x, bank.y - start.y),
                                   "entry_depth_cm": surface - column["bottom_cm"]})
    candidates.sort(key=lambda row: (row["bank_distance_cm"], row["span_cm"]))
    geometry = u.EcoCreatureAnimationBuilder
    for row in candidates:
        bank = u.Vector(*row["bank_cm"])
        middle = geometry.project_placement_point(world, (start + bank) * .5)
        row["ground_sweep_at_reference_body_scale"] = middle is not None and (
            geometry.validate_fauna_ground_segment(world, authored["river"], "Mink", start, middle, 1.)
            and geometry.validate_fauna_ground_segment(world, authored["river"], "Mink", middle, bank, 1.))
        eye = u.Vector(0., 0., 15.)
        row["ground_sight_at_15cm"] = geometry.has_fauna_audit_sight(world, start + eye, bank + eye)
    high_water = [row for row in candidates if row["bank_above_high_water_cm"] > 0.]
    ground_reachable = [row for row in candidates
                        if row["ground_sweep_at_reference_body_scale"] and row["ground_sight_at_15cm"]]
    return {"entry_columns": len(columns), "pair_count": len(high_water), "candidates": high_water[:30],
            "low_water_pair_count": len(candidates), "low_water_candidates": candidates[:30],
            "ground_reachable_pair_count": len(ground_reachable), "ground_reachable_candidates": ground_reachable[:30]}


def survey_mink_flood_exits(world, shore, low_water):
    bank = u.Vector(*shore["shore_point"])
    result["flood_exit_survey"] = survey_mink_shore_geometry(world, bank, low_water)


def survey_mink_shore_geometry(world, bank, low_water, max_bank_distance=None):
    stride = 30.
    cells = {}
    for x in range(-34, 35):
        for y in range(-34, 35):
            point = bank + u.Vector(x * stride, y * stride, 0.)
            hits = u.SystemLibrary.line_trace_multi_for_objects(
                world, point + u.Vector(0., 0., 600.), point - u.Vector(0., 0., 800.),
                [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True) or []
            for hit in hits:
                data = hit.to_tuple()
                if data[10] and "Landscape" in data[10].get_class().get_name():
                    cells[x, y] = (data[5], data[7].z)
                    break
    candidates = []
    for (x, y), (ground, normal_z) in cells.items():
        if (ground.z < low_water + 28. or normal_z < .65
                or (max_bank_distance is not None
                    and math.hypot(ground.x - bank.x, ground.y - bank.y) > max_bank_distance)):
            continue
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                if (x + dx, y + dy) not in cells:
                    continue
                bottom, _ = cells[x + dx, y + dy]
                if low_water - bottom.z < 18.:
                    continue
                entry = u.Vector(bottom.x, bottom.y, low_water - 8.)
                span = (ground - entry).length()
                if span <= 130.:
                    candidates.append({"bank": list(ground.to_tuple()), "entry": list(entry.to_tuple()),
                                       "span_cm": span, "distance_from_original_cm": (ground - bank).length(),
                                       "depth_at_low_water_cm": low_water - bottom.z})
    candidates.sort(key=lambda row: row["distance_from_original_cm"])
    return {"stride_cm": stride, "landscape_samples": len(cells),
            "low_water_z": low_water, "candidate_count": len(candidates), "candidates": candidates[:30]}


def add_eagle_perch_trial(world, runtime):
    perches = [site.copy() for site in runtime.get_editor_property("fauna_perches")]
    result["eagle_perches"] = []
    # Locations from repeated flight arrivals in the no-perch baseline.
    for x, y, z in ((52458., 50838., 3677.), (51314., 49330., 3137.),
                    (49147., 47923., 3129.), (52323., 50251., 3701.)):
        hint = u.Vector(x, y, z)
        point = u.EcoCreatureAnimationBuilder.project_placement_point(world, hint)
        if point is None or abs(point.z - z) > 25.:
            continue
        footprint = [u.EcoCreatureAnimationBuilder.project_placement_point(world, point + offset)
                     for offset in (u.Vector(55., 0., 0.), u.Vector(-55., 0., 0.),
                                    u.Vector(0., 55., 0.), u.Vector(0., -55., 0.))]
        if any(sample is None or abs(sample.z - point.z) > 30. for sample in footprint):
            continue
        site = u.EcoFaunaPerch()
        site.set_editor_property("region_id", "Highland")
        site.set_editor_property("species_id", "GoldenEagle")
        site.set_editor_property("location", point)
        perches.append(site)
        result["eagle_perches"].append(list(point.to_tuple()))
    if not result["eagle_perches"]:
        raise RuntimeError("No golden eagle perch passed the ground survey")
    runtime.set_editor_property("fauna_perches", perches)


def try_second_eagle_perch(world, runtime):
    # Both saved-map seeds show these natural landing neighborhoods for eagle 100.
    hints = ((52187., 50258., 3765.), (51865.31, 50506.02, 3879.94), (52495., 50567., 3728.))
    project = u.EcoCreatureAnimationBuilder.project_placement_point
    highland, = (actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)
                 if str(actor.get_editor_property("region_id")) == "Highland")
    bounds = highland.get_editor_property("region_bounds")
    transform, extent = bounds.get_world_transform(), bounds.get_unscaled_box_extent()
    offsets = (u.Vector(55., 0., 0.), u.Vector(-55., 0., 0.), u.Vector(0., 55., 0.), u.Vector(0., -55., 0.))
    perches = list(runtime.get_editor_property("fauna_perches"))
    trial = {"candidates": [], "added_perch_cm": None, "flight_transitions": [], "probe_step_cm": 40.,
             "probe_radius_cm": 280., "landing_footprint_radius_cm": 55.}
    result["second_eagle_perch"] = trial
    candidates = []
    for coordinates in hints:
        hint = u.Vector(*coordinates)
        hit = u.SystemLibrary.line_trace_single_for_objects(
            world, hint + u.Vector(0., 0., 5000.), hint - u.Vector(0., 0., 20000.),
            [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True)
        checks = {"hint_cm": coordinates, "rejected": {}, "accepted": 0}
        if hit:
            data = hit.to_tuple()
            checks["hint_static_hit"] = {"position_cm": list(data[5].to_tuple()), "normal_z": data[7].z,
                                         "component": data[10].get_class().get_name() if data[10] else None}
        rejected = Counter()
        for x in range(-7, 8):
            for y in range(-7, 8):
                if x * x + y * y > 49:
                    continue
                point = project(world, hint + u.Vector(40. * x, 40. * y, 0.))
                if point is None:
                    rejected["projection"] += 1
                    continue
                local = u.MathLibrary.inverse_transform_location(transform, point)
                if abs(local.x) > extent.x or abs(local.y) > extent.y or abs(local.z) > extent.z:
                    rejected["outside_highland"] += 1
                    continue
                if abs(point.z - hint.z) > 100.:
                    rejected["height_difference"] += 1
                    continue
                if any((site.get_editor_property("location") - point).length() <= 120. for site in perches):
                    rejected["existing_perch"] += 1
                    continue
                footprint = [project(world, point + offset) for offset in offsets]
                if any(sample is None or abs(sample.z - point.z) > 30. for sample in footprint):
                    rejected["uneven_footprint"] += 1
                    continue
                candidates.append(((point - hint).length(), point))
                checks["accepted"] += 1
        checks["rejected"] = dict(rejected)
        trial["candidates"].append(checks)
    if not candidates:
        return
    _, point = min(candidates, key=lambda candidate: candidate[0])
    site = u.EcoFaunaPerch()
    site.set_editor_property("region_id", "Highland")
    site.set_editor_property("species_id", "GoldenEagle")
    site.set_editor_property("location", point)
    runtime.set_editor_property("fauna_perches", [*perches, site])
    trial["added_perch_cm"] = list(point.to_tuple())
    result["eagle_perches"].append(trial["added_perch_cm"])


def sample_eagle_perch_approach(world, now):
    trial = result["second_eagle_perch"]
    if not trial["added_perch_cm"]:
        return
    point = u.Vector(*trial["added_perch_cm"])
    previous = trial.setdefault("last_flight_phase", {})
    for agent in (99, 100):
        row = read_agent(world, agent)
        if not row or row["species"] != "GoldenEagle" or row["hp"] <= 0.:
            continue
        phase = row["rule_fauna"]["flight_phase"]
        if previous.get(str(agent)) == phase:
            continue
        previous[str(agent)] = phase
        position = u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", row["position"])))
        trial["flight_transitions"].append({
            "agent": agent, "world_seconds": now, "phase": phase, "position_cm": list(position.to_tuple()),
            "distance_to_added_perch_cm": (position - point).length(),
        })


def inspect_mink_shore(world, runtime):
    patches = [patch.copy() for patch in runtime.get_editor_property("fauna_habitat_patches")]
    index, = (i for i, patch in enumerate(patches) if str(patch.get_editor_property("id")) == "IslandRiverRoots")
    patch = patches[index]
    region = str(patch.get_editor_property("region_id"))
    root = patch.get_editor_property("center")
    points = []
    shoreline = []
    founders = []
    for group in runtime.get_editor_property("groups"):
        if str(group.get_editor_property("region_id")) == region:
            for placement in group.get_editor_property("fauna"):
                if str(placement.get_editor_property("species_id")) == "Mink":
                    founders.extend(placement.get_editor_property("spawn_points"))
    for agent, founder in enumerate(founders, start=1):
        for step in range(41):
            point = root + (founder - root) * (step / 40.)
            sample = inspect.inspect_fauna_water(world, region, point, 6.)
            ground = u.EcoCreatureAnimationBuilder.project_placement_point(world, point)
            points.append({"agent": str(agent), "point": [point.x, point.y, point.z],
                           "water": [sample[0].x, sample[0].y] if sample else None,
                           "ground": [ground.x, ground.y, ground.z] if ground else None})
        dx, dy = founder.x - root.x, founder.y - root.y
        span = math.hypot(dx, dy)
        if span <= 0.:
            continue
        lateral = u.Vector(-dy / span, dx / span, 0.)
        for offset in (-400., -200., 0., 200., 400.):
            for step in range(121):
                point = root + (founder - root) * (step / 120.) + lateral * offset
                hits = u.SystemLibrary.line_trace_multi_for_objects(
                    world, point + u.Vector(0., 0., 600.), point - u.Vector(0., 0., 1000.),
                    [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True) or []
                bed = None
                for hit in hits:
                    data = hit.to_tuple()
                    if data[10] and "Landscape" in data[10].get_class().get_name():
                        bed = data[5]
                        break
                sample = inspect.inspect_fauna_water(world, region, point, 6.)
                shoreline.append({"agent": str(agent), "offset_cm": offset, "step": step,
                                  "point": [point.x, point.y, point.z],
                                  "landscape_z": bed.z if bed is not None else None,
                                  "water": [sample[0].x, sample[0].y] if sample else None})
    result["shore_profile"] = points
    result["shoreline_landscape_profile"] = shoreline
    # A shallow edge needs both a real dry approach and a usable wet endpoint.
    # Do not treat the last column inside the authored volume as the bank.
    candidates = []
    for agent in sorted({row["agent"] for row in shoreline}):
        for offset in (-400., -200., 0., 200., 400.):
            line = [row for row in shoreline if row["agent"] == agent and row["offset_cm"] == offset]
            for wet, bank in zip(line, line[1:]):
                if not wet["water"] or bank["water"] or bank["landscape_z"] is None:
                    continue
                bottom, surface = wet["water"]
                if bank["landscape_z"] < surface or not 12. <= surface - bottom <= 45.:
                    continue
                candidates.append({"agent": agent,
                                   "bank": [*bank["point"][:2], bank["landscape_z"]],
                                   "entry": [*wet["point"][:2], surface - 6.],
                                   "depth_cm": surface - bottom})
    result["shoreline_geometry_candidates"] = candidates
    # Report where the terrain actually crosses the reference surface, even
    # outside the swimming volumes. These are sites to survey for a connector.
    root_column = inspect.inspect_fauna_water(world, region, root, 6.)
    if root_column:
        surface = root_column[0].y
        crossings = []
        for wet, dry in zip(shoreline, shoreline[1:]):
            if (wet["agent"], wet["offset_cm"]) != (dry["agent"], dry["offset_cm"]):
                continue
            if wet["landscape_z"] is None or dry["landscape_z"] is None:
                continue
            if wet["landscape_z"] < surface <= dry["landscape_z"]:
                crossings.append({"agent": wet["agent"], "offset_cm": wet["offset_cm"],
                                  "wet_ground": [*wet["point"][:2], wet["landscape_z"]],
                                  "dry_ground": [*dry["point"][:2], dry["landscape_z"]],
                                  "reference_surface_z": surface})
        result["shoreline_terrain_crossings"] = crossings


def add_mink_shore_connector(world, runtime):
    crossing = next(row for row in result["shoreline_terrain_crossings"]
                    if row["offset_cm"] == 0. and row["agent"] == result["shore_profile"][0]["agent"])
    rows = [row for row in result["shoreline_landscape_profile"]
            if row["agent"] == crossing["agent"] and row["offset_cm"] == 0.]
    bank = u.Vector(*crossing["dry_ground"])
    surface = crossing["reference_surface_z"]
    entry_ground = next(row for row in reversed(rows)
                        if row["landscape_z"] is not None and 18. <= surface - row["landscape_z"] <= 35.)
    entry = u.Vector(*entry_ground["point"][:2], surface - 8.)
    patches = [patch.copy() for patch in runtime.get_editor_property("fauna_habitat_patches")]
    patch, = (p for p in patches if str(p.get_editor_property("id")) == "IslandRiverRoots")
    root = patch.get_editor_property("center")
    region = str(patch.get_editor_property("region_id"))
    offset = entry - root
    habitat, = (actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoVegetationHabitat)
                if str(actor.get_editor_property("habitat_id")) == "IslandLowerRiver05")
    bounds = habitat.get_editor_property("bounds")
    original_extent = bounds.get_unscaled_box_extent()
    transform = habitat.get_actor_transform()
    local_entry = u.MathLibrary.inverse_transform_location(transform, entry)
    bounds.set_box_extent(u.Vector(max(original_extent.x, abs(local_entry.x) + 75.),
                                  max(original_extent.y, abs(local_entry.y) + 75.),
                                  original_extent.z), True)
    if not habitat.is_valid_habitat():
        raise RuntimeError("Invalid trial swimming connector")
    for i in range(41):
        if not inspect.inspect_fauna_water(world, region, root + offset * (i / 40.), 6.):
            raise RuntimeError(f"Swimming connector lacks depth or collision at sample {i}")
    patch.set_editor_property("has_shore_entry", True)
    patch.set_editor_property("shore_point", bank)
    patch.set_editor_property("water_entry_point", entry)
    food = root
    if result["near_food_trial"]:
        food = entry - offset * (150. / math.hypot(offset.x, offset.y))
        column = inspect.inspect_fauna_water(world, region, food, 6.)
        if not column:
            raise RuntimeError("Near-shore food point has no usable water column")
        floor, surface = column[0].x, column[0].y
        food.z = (floor + surface) * .5
        if result["split_food_trial"]:
            near_patch = patch.copy()
            near_patch.set_editor_property("id", "IslandRiverRootsShore")
            near_patch.set_editor_property("center", food)
            near_patch.set_editor_property("aquatic_nursery", False)
            near_patch.set_editor_property("has_shore_entry", result["validate_shore_on_start"])
            patch.set_editor_property("has_shore_entry", False)
            for name in ("capacity", "regrowth_per_second"):
                total = patch.get_editor_property(name)
                patch.set_editor_property(name, total * .625)
                near_patch.set_editor_property(name, total * .375)
            patches.append(near_patch)
        else:
            patch.set_editor_property("center", food)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    trial_id = "IslandRiverRootsShore" if result["split_food_trial"] else "IslandRiverRoots"
    actual, = (p for p in runtime.get_editor_property("fauna_habitat_patches")
               if str(p.get_editor_property("id")) == trial_id)
    if bool(actual.get_editor_property("has_shore_entry")) != (not result["split_food_trial"] or result["validate_shore_on_start"]) or (
            actual.get_editor_property("water_entry_point") - entry).length() > .01 or (
            actual.get_editor_property("shore_point") - bank).length() > .01 or (
            actual.get_editor_property("center") - food).length() > .01:
        raise RuntimeError("PIE did not retain the mink shore transition points")
    authored["water_samples"]["RootsShore" if result["split_food_trial"] else "Roots"] = [food.x, food.y, food.z]
    result["mink_connector"] = {"bank": [bank.x, bank.y, bank.z], "entry": [entry.x, entry.y, entry.z],
                                "food": [food.x, food.y, food.z], "entry_to_food_cm": (food - entry).length(),
                                "continuous_water_samples": 41, "expanded_habitat": "IslandLowerRiver05",
                                "extent_cm": list(bounds.get_unscaled_box_extent().to_tuple())}
    projected = u.EcoCreatureAnimationBuilder.project_placement_point(world, bank)
    result["mink_connector"]["startup_geometry"] = {
        "projected_bank": list(projected.to_tuple()) if projected is not None else None,
        "projected_bank_to_entry_cm": (projected - entry).length() if projected is not None else None,
        "entry_column": str(inspect.inspect_fauna_water(world, region, entry, 4.)),
    }


def move_trial_patch(runtime):
    # World Partition PIE can reload the external actor from its saved package.
    # Edit the PIE instance after its stock array has been initialized.
    patches = [patch.copy() for patch in runtime.get_editor_property("fauna_habitat_patches")]
    index, = (i for i, patch in enumerate(patches)
              if str(patch.get_editor_property("id")) == "IslandRiverSlowShelf")
    old = patches[index].get_editor_property("center")
    original_center = [old.x, old.y, old.z]
    reference, depth_offset = {"roots": ("Roots", 85.), "shelf": ("Drift", -25.),
                               "inlet": ("InletPlants", 40.)}[result["layout"]]
    candidate = u.Vector(*authored["water_samples"][reference]) + u.Vector(0., 0., depth_offset)
    patches[index].set_editor_property("center", candidate)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    actual = runtime.get_editor_property("fauna_habitat_patches")[index].get_editor_property("center")
    if (actual - candidate).length() > .01 or (actual - u.Vector(*original_center)).length() < 1.:
        raise RuntimeError(f"PIE patch relocation mismatch: original={original_center}, "
                           f"requested={candidate}, actual={actual}")
    authored["water_samples"]["SlowShelf"] = [actual.x, actual.y, actual.z]
    result["moved_patch"] = {"id": "IslandRiverSlowShelf", "from": original_center,
                             "to": [actual.x, actual.y, actual.z]}


def sample_saved_transition_habitat(world, runtime, now):
    region_id = result["transition_authoring"]["region_id"]
    regions = {str(a.get_editor_property("region_id")): a for a in
               u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)}
    river = regions["Riverbank"].get_environment_state()
    habitat = regions[region_id].get_environment_state()
    actual = {field: habitat.get_editor_property(field) for field in ("rainfall", "temperature", "humidity")}
    expected = ({"rainfall": result["local_forage_soil"]["rain_events"][-1]["rainfall"], "temperature": 18.}
                if local_soil_trial else {field: river.get_editor_property(field) for field in actual})
    if any(abs(actual[field] - value) > .01 for field, value in expected.items()):
        raise RuntimeError(f"Saved transition weather differs from the expected input at {now:.2f}: {actual}")
    visuals = {str(a.get_editor_property("patch_id")): a for a in
               u.GameplayStatics.get_all_actors_of_class(world, u.EcoForagePatchVisual)}
    fractions = {}
    for name in ("IslandForageWestForbs", "IslandTransitionForbs"):
        stock = runtime.inspect_fauna_habitat_stock(name)
        fraction = (stock[-1] if isinstance(stock, tuple) else stock) / 4.5
        visual = visuals[name]
        visible = visual.get_forage_fraction()
        if abs(fraction - visible) > .005:
            raise RuntimeError(f"Saved forage visual {name} does not match stock")
        fractions[name] = {"stock_fraction": fraction, "visual_fraction": visible,
                           "instances": visual.get_editor_property("plants").get_instance_count()}
    sample = {"time": now, "climate": actual, "forage": fractions}
    result.setdefault("transition_saved_samples", []).append(sample)
    return sample


def save_verified_highland_approach():
    target = "/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed"
    if editor.get_editor_world().get_path_name().split(".")[0] != target:
        raise RuntimeError("Save the verified approach on the owned island only")
    runs = [json.loads((out.parent / f"Island_{seed}_highland_pie_access" / "IslandFaunaPIE.json").read_bytes())
            for seed in (20000, 20017)]
    if any(run["errors"] or len(run["samples"]) < 43 or not all(run["highland_approach_trial_checks"].values())
           for run in runs):
        raise RuntimeError("Both Highland approach runs must pass the ground checks")
    added = runs[0]["highland_approach_points"]
    if not added or added != runs[1]["highland_approach_points"]:
        raise RuntimeError("Highland approach differs between the two runs")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    route, = (actor for actor in actors.get_all_level_actors()
              if isinstance(actor, u.EcoHerdMigrationRoute)
              and str(actor.get_editor_property("from_region")) == "Highland"
              and str(actor.get_editor_property("to_region")) == transition_geometry()["region_id"])
    points = list(route.get_editor_property("points"))
    prefix = [u.Vector(*point) for point in reversed(added)]
    if len(points) >= len(prefix) and all((a - b).length() <= .01 for a, b in zip(points, prefix)):
        u.log("ECO_ISLAND_HIGHLAND_APPROACH_ALREADY_SAVED")
        return
    if not points or (points[0] - u.Vector(47000., 49600., 3137.18)).length() > 1.:
        raise RuntimeError("Saved Highland route start differs from the verified baseline")
    route.modify()
    route.set_editor_property("points", [*prefix, *points])
    if not route.is_valid_route() or not levels.save_current_level():
        raise RuntimeError("Could not save the verified Highland approach")
    u.log("ECO_ISLAND_HIGHLAND_APPROACH_SAVED")


def stage_grassland_budget_shift(mode):
    runtime, = (actor for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                if isinstance(actor, u.EcoCreatureIntegrationSpawner))
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    by_id = {str(patch.get_editor_property("id")): patch for patch in patches}
    source_id = "IslandForageFloodplainApproach"
    target_id = "IslandForageWestMeadow"
    source, target = by_id[source_id], by_id[target_id]
    fields = ("capacity", "regrowth_per_second")
    before = {patch_id: {field: by_id[patch_id].get_editor_property(field) for field in fields}
              for patch_id in (source_id, target_id)}
    transfers = {"Both": (3., .04), "Capacity": (3., 0.), "Regrowth": (0., .04)}
    for field, transfer in zip(fields, transfers[mode]):
        source.set_editor_property(field, before[source_id][field] - transfer)
        target.set_editor_property(field, before[target_id][field] + transfer)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    result["grassland_budget_shift"] = {"mode": mode, "before": before, "after": {
        patch_id: {field: by_id[patch_id].get_editor_property(field) for field in fields}
        for patch_id in (source_id, target_id)}}


def stage_deep_shelf():
    runtime, = (actor for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                if isinstance(actor, u.EcoCreatureIntegrationSpawner))
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    shelf, = (patch for patch in patches if str(patch.get_editor_property("id")) == "IslandRiverSlowShelf")
    center = shelf.get_editor_property("center")
    original = list(center.to_tuple())
    candidate = u.Vector(*authored["water_samples"]["InletPlants"]) + u.Vector(0., 0., deep_shelf_offset_cm)
    if (candidate - center).length() <= .01:
        result["deep_shelf_start"] = {"original_cm": original, "trial_cm": original}
        return
    if (candidate + u.Vector(0., 0., 72.) - center).length() > .01:
        raise RuntimeError("The shelf center differs from the surveyed baseline")
    shelf.set_editor_property("center", candidate)
    runtime.modify()
    runtime.set_editor_property("fauna_habitat_patches", patches)
    result["deep_shelf_start"] = {"original_cm": original, "trial_cm": list(candidate.to_tuple())}


def stage_mink_bank_layout(persist=False):
    evidence = out.parent
    runs = [json.loads((evidence / f"Island_{seed}_mink_dry_continuation" /
                        "IslandFaunaPIE.json").read_bytes()) for seed in (20000, 20017)]
    flood = runs[0]["second_mink_flood"]
    ramp = flood["ramp"]
    if any(run["errors"] or run["second_mink_flood"]["ramp"] != ramp
           or not run["second_mink_flood"].get("dry_ground_arrival", {}).get("before_restore") for run in runs):
        raise RuntimeError("Both mink runs must reach the same dry bank")
    trial = runs[0]["second_mink_trial"]
    world = editor.get_editor_world()
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    runtime, = (actor for actor in actors.get_all_level_actors() if isinstance(actor, u.EcoCreatureIntegrationSpawner))
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    if any(str(p.get_editor_property("id")) == "IslandRiverSecondMinkShore" for p in patches):
        raise RuntimeError("Second mink layout is already present")
    patches_by_id = {str(p.get_editor_property("id")): p for p in patches}
    donor = patches_by_id[trial["donor_patch"]]
    local = patches_by_id["IslandRiverRootsShore"].copy()
    for field, transfer in trial["budget"].items():
        if not math.isclose(donor.get_editor_property(field), transfer["before"], abs_tol=.00001):
            raise RuntimeError(f"Unexpected original mink forage {field}")
        donor.set_editor_property(field, transfer["existing"])
        local.set_editor_property(field, transfer["local"])
    for field, value in {"id": "IslandRiverSecondMinkShore", "center": u.Vector(*trial["food_cm"]),
                         "water_entry_point": u.Vector(*trial["candidate"]["entry_cm"]),
                         "shore_point": u.Vector(*flood["platform_cm"]),
                         "dry_bank_point": u.Vector(*ramp["dry_bank_cm"])}.items():
        local.set_editor_property(field, value)
    base, end = (u.Vector(*ramp[key]) for key in ("base_cm", "end_cm"))
    rotation = u.MathLibrary.find_look_at_rotation(base, end)
    spawn_mink_walk_surface(world, (base + end) * .5, rotation,
                            u.Vector(ramp["span_cm"] / 100., ramp["width_cm"] / 100., .14), authored_actor=True)
    groups = list(runtime.get_editor_property("groups"))
    group, = (g for g in groups if str(g.get_editor_property("region_id")) == authored["river"])
    fauna = list(group.get_editor_property("fauna"))
    mink, = (f for f in fauna if str(f.get_editor_property("species_id")) == "Mink")
    points = list(mink.get_editor_property("spawn_points"))
    if len(points) != 2 or (points[1] - u.Vector(*trial["near_start_cm"])).length() < 20.:
        raise RuntimeError("Unexpected original mink founder placement")
    points[1] = u.Vector(*ramp["dry_bank_cm"])
    mink.set_editor_property("spawn_points", points)
    group.set_editor_property("fauna", fauna)
    runtime.modify()
    runtime.set_editor_property("groups", groups)
    runtime.set_editor_property("fauna_habitat_patches", [*patches, local])
    result["second_mink_bank_layout"] = {"ramp": ramp, "trial": trial, "platform_cm": flood["platform_cm"]}
    if persist and not levels.save_current_level():
        raise RuntimeError("Could not save the verified mink exit")


def dress_saved_mink_bank():
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    existing = actors.get_all_level_actors()
    ramp, = (a for a in existing if a.get_actor_label() == "JYU_LowerRiver_DryBankShelf")
    if any(a.get_actor_label().startswith("JYU_LowerRiver_BankStone") for a in existing):
        raise RuntimeError("The saved ramp already has a visual surface")
    assets = [u.load_asset(f"/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Cover/SM_MWAM_Stone{suffix}")
              for suffix in ("A", "B", "C")]
    if not all(assets):
        raise RuntimeError("Missing the island's existing stone meshes")
    base = ramp.get_actor_location()
    rotation = ramp.get_actor_rotation()
    forward = u.MathLibrary.get_forward_vector(rotation)
    right = u.MathLibrary.get_right_vector(rotation)
    up = u.MathLibrary.get_up_vector(rotation)
    scale = ramp.get_actor_scale3d()
    ramp.modify()
    component = ramp.static_mesh_component
    component.modify()
    component.set_visibility(False)
    component.set_cast_shadow(False)
    for index, (distance, side, width, height) in enumerate((
            (-252., -4., 142., 32.), (-151., 13., 151., 27.), (-52., -9., 149., 42.),
            (47., 8., 164., 35.), (149., -7., 155., 28.), (248., 9., 143., 31.))):
        stone = assets[index % len(assets)]
        bounds = stone.get_bounding_box()
        size = bounds.max - bounds.min
        center = (bounds.min + bounds.max) * .5
        stone_scale = u.Vector(128. / size.x, width / size.y, height / size.z)
        stone_top = base + forward * distance + right * side + up * (scale.z * 50. - 1.)
        pivot = stone_top - forward * (center.x * stone_scale.x) - right * (center.y * stone_scale.y)
        pivot = pivot - up * (bounds.max.z * stone_scale.z)
        actor = actors.spawn_actor_from_class(u.StaticMeshActor, pivot, rotation)
        actor.set_actor_label(f"JYU_LowerRiver_BankStone_{index + 1:02d}")
        actor.set_actor_scale3d(stone_scale)
        actor.static_mesh_component.set_static_mesh(stone)
        actor.static_mesh_component.set_collision_profile_name("NoCollision")
    if not levels.save_current_level():
        raise RuntimeError("Could not save the mink ramp presentation")
    u.log("ECO_ISLAND_MINK_BANK_SURFACE_SAVED")


def save_verified_deep_shelf():
    evidence = out.parent
    for seed in (20000, 20017):
        for label in ("fry_shelf_start", "fry_shelf_high", "fry_shelf_restore"):
            report_path = evidence / f"Island_{seed}_{label}" / "IslandFaunaPIE.json"
            report = json.loads(report_path.read_bytes())
            hatch = str(report["nursery_fry"]["hatch"]["related_id"])
            log = (evidence / "IslandAccessBaseline" / f"{seed}_{label}.log").read_text(encoding="utf-8")
            agents = set(re.findall(r"\[PatchMeal\] Patch=IslandRiverSlowShelf Species=CommonCarp Agent=(\d+)", log))
            if report["errors"] or len(report["samples"]) < 49 or hatch not in agents or len(agents) < 2:
                raise RuntimeError(f"Shelf feeding evidence missing for {seed} {label}")
    if not (evidence / "Island_20017_fry_shelf_render" / "IslandFauna_DeepShelf.png").is_file():
        raise RuntimeError("Missing underwater visual evidence")
    stage_deep_shelf()
    if not levels.save_current_level():
        raise RuntimeError("Could not save the verified deep shelf")
    u.log("ECO_ISLAND_DEEP_SHELF_SAVED")


def begin():
    if second_mink_remove_exit_cover and not second_mink_exit_cover:
        raise RuntimeError("Removing mink exit cover requires the cover trial")
    if second_mink_exit_cover and not (second_mink_flood and second_mink_flood_platform and audit_label):
        raise RuntimeError("Mink exit cover requires a labeled flood platform trial")
    if focused_mink_ramp and not (second_mink_flood and second_mink_flood_ramp and second_mink_flood_platform
                                and second_mink_flood_cover_bank and second_mink_near_start
                                and second_mink_trial is not None and audit_label):
        raise RuntimeError("Focused mink ramp requires the labeled flood, bank, ramp and near-start trial")
    if editor.get_editor_world().get_name() != authored["map"].rsplit("/", 1)[-1]:
        raise RuntimeError("Open the island copy first")
    if "-EcoIslandVerifySnowStageBounds" in command.split():
        region, = (actor for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                   if isinstance(actor, u.EcologyRegion) and str(actor.get_editor_property("region_id")) == "Snowfield")
        extent = list(region.get_editor_property("region_bounds").get_unscaled_box_extent().to_tuple())
        if extent != [6000., 6000., 2500.]:
            raise RuntimeError(f"The saved Snowfield boundary is {extent}")
        result["saved_snow_stage_extent_cm"] = extent
    if "-EcoIslandVerifyGrasslandStageBounds" in command.split():
        region, = (actor for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                   if isinstance(actor, u.EcologyRegion) and str(actor.get_editor_property("region_id")) == "Grassland")
        bounds = region.get_editor_property("region_bounds")
        extent = list(bounds.get_unscaled_box_extent().to_tuple())
        center = list(bounds.get_world_location().to_tuple())
        if extent != [6000., 5100., 2500.] or center[:2] != [90000., 60900.]:
            raise RuntimeError(f"The saved Grassland boundary is {extent} at {center}")
        result["saved_grass_stage_bounds"] = {"extent_cm": extent, "center_cm": center}
    save_grass = "-EcoIslandSaveGrasslandStageBounds" in command.split()
    if save_grass or "-EcoIslandSaveSnowStageBounds" in command.split():
        region_name = "Grassland" if save_grass else "Snowfield"
        label = "grass_stage_bounds" if save_grass else "snow_stage_bounds"
        target = "/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed"
        if editor.get_editor_world().get_path_name().split(".")[0] != target:
            raise RuntimeError("Save the verified boundary only on the owned island")
        expected = [6000., 5100., 2500.] if save_grass else [6000., 6000., 2500.]
        for trial_seed in (20000, 20017):
            path = out.parent / f"Island_{trial_seed}_{label}" / "IslandFaunaPIE.json"
            trial = json.loads(path.read_text(encoding="utf-8-sig"))
            changes = trial["native_stage_bounds"]
            if (trial["errors"] or changes["changed_membership"] or changes["surveyed_points"] != 107
                    or changes["regions"][region_name]["after_extent_cm"] != expected
                    or (save_grass and changes["regions"][region_name]["after_center_cm"][:2] != [90000., 60900.])
                    or not trial["second_mink_flood"]["dry_ground_arrival"]["before_restore"]):
                raise RuntimeError(f"{region_name} boundary trial did not pass for seed {trial_seed}")
        region, = (actor for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                   if isinstance(actor, u.EcologyRegion) and str(actor.get_editor_property("region_id")) == region_name)
        bounds = region.get_editor_property("region_bounds")
        actual = list(bounds.get_unscaled_box_extent().to_tuple())
        center = bounds.get_world_location()
        if actual != expected:
            if actual != [4200., 4200., 2500.]:
                raise RuntimeError(f"Unexpected {region_name} bounds {actual}")
            region.modify()
            bounds.modify()
            bounds.set_box_extent(u.Vector(*expected), False)
            if save_grass:
                if abs(center.x - 90000.) > .01 or abs(center.y - 60000.) > .01:
                    raise RuntimeError("Unexpected original Grassland center")
                bounds.set_world_location(center + u.Vector(0., 900., 0.), False, True)
            if not levels.save_current_level():
                raise RuntimeError(f"Could not save the {region_name} boundary")
        u.log("ECO_ISLAND_GRASS_STAGE_BOUNDS_SAVED" if save_grass else "ECO_ISLAND_SNOW_STAGE_BOUNDS_SAVED")
        u.SystemLibrary.quit_editor()
        return None
    if "-EcoIslandDeepShelfStart" in command.split():
        stage_deep_shelf()
    if second_mink_bank_layout:
        stage_mink_bank_layout()
    if combat_trial:
        world = editor.get_editor_world()
        asset = u.load_asset("/Game/JWJ/Gameplay/BP_EcoGameMode_Common")
        mode = u.BlueprintEditorLibrary.generated_class(asset) if asset else None
        if not mode:
            raise RuntimeError("Team combat game mode asset missing")
        world.get_world_settings().set_editor_property("default_game_mode", mode)
        runtime, = (a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                    if isinstance(a, u.EcoCreatureIntegrationSpawner))
        runtime.set_editor_property("enable_player_combat", True)
    if result.get("save_highland_approach"):
        save_verified_highland_approach()
        u.SystemLibrary.quit_editor()
        return None
    if (result.get("transition_habitat_author") or result["save_grassland_passage"]
            or result["hold_grassland_passage"] or save_water_forage or save_deep_shelf or save_mink_bank_layout
            or save_island_deer_presentation or save_island_weather or save_mink_bank_surface or save_river_rat_refuge):
        target = "/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed"
        if (editor.get_editor_world().get_path_name().split(".")[0] != target
                or (result.get("transition_habitat_author") and (
                    not result.get("transition_habitat_river_approach") or result.get("transition_habitat_founder")))):
            raise RuntimeError("Save only the verified layout to the owned island")
        partition = u.WorldPartitionBlueprintLibrary
        descs = partition.get_actor_descs()
        prefix = target.replace("/Game/", "/Game/__ExternalActors__/", 1) + "/"
        if not descs or any(not str(row.get_editor_property("actor_package")).startswith(prefix) for row in descs):
            raise RuntimeError("Unexpected actor package outside the owned island")
        partition.load_actors([row.get_editor_property("guid") for row in descs])
    if save_river_rat_refuge:
        world = editor.get_editor_world()
        runtime, = (actor for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                    if isinstance(actor, u.EcoCreatureIntegrationSpawner))
        trial = apply_river_rat_refuge_trial(world, runtime, "ApproachCovered", persist=True)
        # The ground sweep needs the region subsystem registered in PIE. Candidate collision was verified there.
        measure_river_rat_cover(world, runtime, trial["sites"], aligned=True, persist=True)
        if not levels.save_current_level():
            raise RuntimeError("Could not save the Riverbank refuge layout")
        u.log("ECO_ISLAND_RIVER_RAT_REFUGE_SAVED")
        u.SystemLibrary.quit_editor()
        return None
    if save_mink_bank_surface:
        dress_saved_mink_bank()
        u.SystemLibrary.quit_editor()
        return None
    if save_island_weather:
        actors = u.get_editor_subsystem(u.EditorActorSubsystem)
        available = actors.get_all_level_actors()
        writers = {str(region) for actor in available if isinstance(actor, u.EcoRegionEnvironmentAdapter)
                   and (actor.get_editor_property("cycle_rainfall") or actor.get_editor_property("apply_authored_weather"))
                   for region in actor.get_editor_property("region_ids")}
        if not {"Snowfield", "Grassland", "Riverbank", "Highland"} <= writers:
            raise RuntimeError("Expected the existing JYU authority weather providers")
        weather_classes = {"BP_SHC_RainRegionalWeather_C", "BP_SHC_SnowRegionalWeather_C"}
        legacy = [actor for actor in available if actor.get_class().get_name() in weather_classes]
        if {actor.get_class().get_name() for actor in legacy} != weather_classes:
            raise RuntimeError("Could not identify the copied weather presentation")
        for actor in legacy:
            u.log(f"Removing copied weather presentation: {actor.get_path_name()}")
            if not actors.destroy_actor(actor):
                raise RuntimeError("Could not remove a duplicate weather presentation")
        if not levels.save_current_level():
            raise RuntimeError("Could not save the island weather presentation")
        u.log("ECO_ISLAND_WEATHER_PRESENTATION_SAVED")
        u.SystemLibrary.quit_editor()
        return None
    if save_island_deer_presentation:
        actors = u.get_editor_subsystem(u.EditorActorSubsystem)
        runtime, = (actor for actor in actors.get_all_level_actors() if isinstance(actor, u.EcoCreatureIntegrationSpawner))
        deer_class = u.load_class(None, "/Game/JYU/Ecosystem/Natural/BP_EcoNaturalDeer.BP_EcoNaturalDeer_C")
        variants = list(u.get_default_object(deer_class).get_editor_property("appearance_variants"))
        for index, mesh in ((1, "SK_DeerStag"), (2, "SK_DeerDoe"), (3, "SK_DeerDoe")):
            if (mesh not in variants[index].get_editor_property("mesh").get_name()
                    or not variants[index].get_editor_property("animation_class")):
                raise RuntimeError(f"Missing existing deer appearance {index}")
        runtime.modify()
        runtime.set_editor_property("herbivore_actor_class", deer_class)
        if not levels.save_current_level():
            raise RuntimeError("Could not save the island deer presentation")
        u.log("ECO_ISLAND_DEER_PRESENTATION_SAVED")
        u.SystemLibrary.quit_editor()
        return None
    if save_mink_bank_layout:
        for seed in (20000, 20017):
            report = json.loads((out.parent / f"Island_{seed}_mink_bank_roundtrip" / "IslandFaunaPIE.json").read_bytes())
            if report["errors"] or not report.get("second_mink_bank_events"):
                raise RuntimeError(f"Complete mink round trip required for seed {seed}")
        stage_mink_bank_layout(persist=True)
        u.log("ECO_ISLAND_MINK_BANK_SAVED")
        u.SystemLibrary.quit_editor()
        return None
    if save_deep_shelf:
        save_verified_deep_shelf()
        u.SystemLibrary.quit_editor()
        return None
    if save_water_forage:
        save_verified_drift_forage()
        u.SystemLibrary.quit_editor()
        return None
    if result["hold_grassland_passage"]:
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        runtime, = (actor for actor in actors if isinstance(actor, u.EcoCreatureIntegrationSpawner))
        routes = [actor for actor in actors if isinstance(actor, u.EcoHerdMigrationRoute)
                  and str(actor.get_editor_property("to_region")) == GRASSLAND_TRANSIT_REGION]
        if len(routes) != 2:
            raise RuntimeError("Expected both saved Grassland routes")
        for route in routes:
            route.modify()
            route.set_editor_property("enabled", False)
        report = json.loads((out.parent / "Island_20000_grassland_sparse" / "IslandFaunaPIE.json").read_bytes())
        move_grassland_forage(actors, runtime, "IslandForageNorthForbs",
                              u.Vector(*report["grassland_forage_move"]["original_cm"]), True)
        if not levels.save_current_level():
            raise RuntimeError("Could not hold the Grassland passage")
        u.log("ECO_ISLAND_GRASSLAND_PASSAGE_HELD")
        u.SystemLibrary.quit_editor()
        return None
    if result.get("record_gameplay_reasons"):
        u.SystemLibrary.execute_console_command(editor.get_editor_world(), "eco.Inspection.GameplayReasons 1")
    if result.get("transition_habitat_saved"):
        result["transition_authoring"] = transition_geometry()
    elif result.get("transition_region_trial"):
        author_transition_region()
    if result.get("grassland_passage_trial"):
        author_grassland_passage()
    budget_shift = re.search(r"(?:^|\s)-EcoIslandGrasslandBudgetShift(?:=(Both|Capacity|Regrowth))?(?:\s|$)", command)
    if budget_shift:
        stage_grassland_budget_shift(budget_shift[1] or "Both")
    if result["grassland_forage_network"]:
        stage_grassland_forage_network()
    if grassland_existing_route_trial:
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        routes = [actor for actor in actors if isinstance(actor, u.EcoHerdMigrationRoute)
                  and str(actor.get_editor_property("to_region")) == GRASSLAND_TRANSIT_REGION]
        if len(routes) != 2 or any(route.get_editor_property("enabled") for route in routes):
            raise RuntimeError("Expected both held Grassland routes")
        for route in routes:
            route.set_editor_property("enabled", True)
    if water_forage_split or water_forage_shared:
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        runtime, = (actor for actor in actors if isinstance(actor, u.EcoCreatureIntegrationSpawner))
        if water_forage_shared:
            if water_forage_split or not (population_duration or result["checkpoint_mode"]):
                raise RuntimeError("Shared water forage trial requires a Population or checkpoint run and its own control")
            patches = list(runtime.get_editor_property("fauna_habitat_patches"))
            drift, = (p for p in patches if str(p.get_editor_property("id")) == "IslandRiverDrift")
            roots, = (p for p in patches if str(p.get_editor_property("id")) == "IslandRiverRoots")
            if drift.get_editor_property("forage_access_points"):
                raise RuntimeError("Expected a Drift patch without extra feeding points")
            point = roots.get_editor_property("center") + u.Vector(65., 0., 91.)
            drift.set_editor_property("forage_access_points", [point])
            if drift_seasonal_trial:
                drift.set_editor_property("seasonal_full_growth_depth_cm", 80.)
                drift.set_editor_property("seasonal_dry_loss_per_second", .065)
                if drift_visual_trial:
                    stage_seasonal_drift_visual(drift)
                if drift_surface_trial:
                    habitat = seasonal_drift_habitat(actors)
                    habitat.set_editor_property("draw_water_surface", True)
                    habitat.set_editor_property("water_surface_size_cm", u.Vector2D(4000., 4000.))
                    if drift_shore_trial:
                        stage_seasonal_drift_shore(drift.get_editor_property("center"), habitat)
            runtime.set_editor_property("fauna_habitat_patches", patches)
            result["water_forage_split"] = {"patch": "IslandRiverDrift", "center_cm": list(point.to_tuple()), "shared": True}
        else:
            result["water_forage_split"] = stage_water_forage_split(runtime)
    if result["save_grassland_passage"]:
        for seed in (20000, 20017):
            report = json.loads((out.parent / f"Island_{seed}_grassland_sparse" / "IslandFaunaPIE.json").read_bytes())
            log = (out.parent / "IslandAccessBaseline" / f"{seed}_grassland_sparse.log").read_text(encoding="utf-8")
            checks = report["grassland_passage"]["ground_checks"]
            tracks = {(row[0], row[3]) for row in report["transition_events"] if row[2] in (GRASSLAND_TRANSIT_REGION, "LowerRiver")}
            fed = set(re.findall(r"\[PatchMeal\] Patch=IslandForageNorthForbs Species=Horse Agent=(\d+) Amount=", log))
            if (report["errors"] or len(report["samples"]) < 43
                    or not all(all(legs) for scales in checks.values() for legs in scales.values())
                    or not any((agent, "PassageTransitEntered") in tracks and (agent, "PassageArrived") in tracks for agent in fed)):
                raise RuntimeError(f"Grassland passage is not ready to save for seed {seed}")
        author_grassland_passage()
        if not levels.save_current_level():
            raise RuntimeError("Could not save the verified Grassland passage")
        u.log("ECO_ISLAND_GRASSLAND_PASSAGE_SAVED")
        u.SystemLibrary.quit_editor()
        return None
    if result.get("transition_habitat_author"):
        if not levels.save_current_level():
            raise RuntimeError("Failed to save the owned island transition habitat")
        u.log("ECO_ISLAND_TRANSITION_HABITAT_SAVED")
        u.SystemLibrary.quit_editor()
        return None
    if result.get("shore_rain_trial"):
        actors = u.get_editor_subsystem(u.EditorActorSubsystem)
        river = authored["river"]
        for actor in actors.get_all_level_actors():
            if isinstance(actor, u.EcoRegionEnvironmentAdapter) and (
                actor.get_editor_property("cycle_rainfall") or actor.get_editor_property("apply_authored_weather")
            ) and (not actor.get_editor_property("region_ids")
                   or river in {str(region) for region in actor.get_editor_property("region_ids")}):
                raise RuntimeError("LowerRiver already has a weather writer")
        adapter = actors.spawn_actor_from_class(u.EcoRegionEnvironmentAdapter, u.Vector())
        adapter.set_editor_property("is_spatially_loaded", False)
        adapter.set_editor_property("region_ids", [river])
        adapter.set_editor_property("rain_cycle_seconds", 120.)
        adapter.set_editor_property("wet_rainfall", 1.)
        adapter.set_editor_property("dry_rainfall", 0.)
        adapter.set_editor_property("cycle_rainfall", True)
    levels.editor_request_begin_play()
    return u.register_slate_post_tick_callback(tick)


if __name__ == "__main__":
    try:
        handle = begin()
    except Exception:
        u.log_error(traceback.format_exc())
        u.SystemLibrary.quit_editor()

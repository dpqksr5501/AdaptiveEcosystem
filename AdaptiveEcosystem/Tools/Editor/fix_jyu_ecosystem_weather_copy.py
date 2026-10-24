"""Targeted owned-map correction. Never regenerate the map or edit team BP assets."""
import json
from pathlib import Path
import unreal

target='/Game/JYU/Maps/LV_JYU_Ecosystem'
owner='JYU.Ecosystem.SoilV1.20261023'
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not levels.load_level(target):raise RuntimeError('Owned map not loaded')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if not world.get_path_name().startswith(target+'.'):raise RuntimeError('Source map refused')
if unreal.EditorAssetLibrary.get_metadata_tag(world,'JYUOwner')!=owner:raise RuntimeError('Owner mismatch')
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Partition not ready')
removed=[]
for actor in actors.get_all_level_actors():
    if actor.get_class().get_name() in ('BP_WeatherManager_C','BP_WeatherManager_PlayerFollow_C'):
        removed.append(dict(label=actor.get_actor_label(),actor=actor.get_path_name(),cls=actor.get_class().get_path_name()))
        if not actors.destroy_actor(actor):raise RuntimeError('Copy actor removal failed')
if removed and not levels.save_current_level():raise RuntimeError('Copy save failed')
remaining=[a.get_path_name() for a in actors.get_all_level_actors()
    if a.get_class().get_name() in ('BP_WeatherManager_C','BP_WeatherManager_PlayerFollow_C')]
if remaining:raise RuntimeError('Duplicate visual weather still present')
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'EcosystemBP_20261023'
(out/'WeatherCopyFix.json').write_text(json.dumps(dict(map=target,removed=removed,remaining=remaining),ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('ECOSYSTEM_WEATHER_COPY_FIXED '+str(len(removed)))

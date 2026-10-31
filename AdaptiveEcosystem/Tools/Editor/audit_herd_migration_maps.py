"""Read-only candidate-level inventory. Never save source levels or source assets."""
import json
from pathlib import Path
import unreal

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
rows=[]
for path in ('/Game/JWJ/Integration_JwJ','/Game/Map/LV_Ecosystem_IntegrationTest','/Game/Map/OpenWorld'):
    if not levels.load_level(path):
        rows.append({'map':path,'loaded':False});continue
    world=editor.get_editor_world()
    selected=[]
    for actor in actors.get_all_level_actors():
        if isinstance(actor,(unreal.EcologyRegion,unreal.EcoCreatureIntegrationSpawner,unreal.EcoShelterAnchor)):
            r={'label':actor.get_actor_label(),'class':actor.get_class().get_path_name(),'position':str(actor.get_actor_location())}
            for key in ('region_id','adjacent_region_ids','arrival_offset','groups','b_use_v3_policy','use_v3_policy','use_habitat_streaming'):
                try:r[key]=str(actor.get_editor_property(key))
                except Exception:pass
            selected.append(r)
    rows.append({'map':path,'loaded':True,'actors_loaded':len(actors.get_all_level_actors()),'runtime':selected,
        'game_mode':str(world.get_world_settings().get_editor_property('default_game_mode'))})
profile=unreal.load_asset('/Game/JYU/Animation/DA_JYU_DeerAnimation')
bones=[]
for path in ('/Game/JYU/Animation/DA_JYU_Deer','/Game/JYU/Animation/DA_JYU_DeerAnimation'):
    obj=unreal.load_asset(path)
    if obj:
        try:
            sk=obj.get_editor_property('locomotion').get_editor_property('skeleton')
            bones=[str(n) for n in unreal.SkeletonEditorLibrary.get_bone_names(sk)]
        except Exception:pass
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'HerdMigration_20261022'
out.mkdir(parents=True,exist_ok=True)
(out/'MapAudit.json').write_text(json.dumps({'maps':rows,'bones':bones},ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('HERD_MAP_AUDIT_FINISHED')

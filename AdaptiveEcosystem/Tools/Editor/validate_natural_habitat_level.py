"""Read-only survey of the currently open level. Does not load/save/change any map."""
import json,re
from pathlib import Path
import unreal

world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
runtimes=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoCreatureIntegrationSpawner)
if len(runtimes)!=1:raise RuntimeError('Keep exactly one supported ecosystem coordinator in the open level')
report=json.loads(runtimes[0].capture_habitat_authoring_report())
name=re.sub(r'[^A-Za-z0-9_]+','_',world.get_name())
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'HabitatAuthoring'
out.mkdir(parents=True,exist_ok=True)
(out/(name+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('HABITAT_SURVEY '+json.dumps(report,ensure_ascii=False))

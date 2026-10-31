"""Observe only received representation and refuge readiness on a real network client."""
import json,re,time
from pathlib import Path
import unreal
cmd=unreal.SystemLibrary.get_command_line()
match=re.search(r'-HerdClientName=(\w+)',cmd)
if not match:raise RuntimeError('Client name required')
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'HerdMigration_20261022'
state={'start':None,'samples':[],'next':0,'best':[]}
def tick(dt):
    game=next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name()=='LV_JYU_HerdMigration'),None)
    if not game:return
    if state['start'] is None:state['start']=time.monotonic()
    elapsed=time.monotonic()-state['start']
    if elapsed<state['next']:return
    state['next']=elapsed+1
    refuges=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoRefugeHabitat)
    visuals=[a for a in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureRepresentationActor) if a.get_editor_property('bound')]
    rows=[]
    for actor in visuals:
        v=actor.get_editor_property('visual_state');rows.append({'id':str(v.get_editor_property('stable_agent_id')),
            'region':str(v.get_editor_property('region_id')),'activity':str(v.get_editor_property('activity'))})
    state['samples'].append({'elapsed':elapsed,'visuals':rows})
    if len(rows)>len(state['best']):state['best']=rows
    if elapsed<18:return
    ids=unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(game)
    ready=sum(a.get_editor_property('registration_ready') for a in refuges)
    visible=sum(a.get_editor_property('brush').is_visible() and a.get_editor_property('brush').get_instance_count()>50 for a in refuges)
    result={'client':match.group(1),'refuges':len(refuges),'ready':ready,'visible':visible,'authority_agents':len(ids),'visuals':state['best'],
        'observations':state['samples'],'local_migration_subsystems':sum(s.get_outer()==game for s in unreal.ObjectIterator(unreal.EcoHerdMigrationSubsystem))}
    result['passed']=len(refuges)==ready==visible==12 and len(ids)==0 and len(state['best'])>0 and result['local_migration_subsystems']==0
    (out/(match.group(1)+'_Client.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    unreal.log('HERD_CLIENT_FINISHED '+json.dumps(result))
    unreal.unregister_slate_post_tick_callback(handle)
handle=unreal.register_slate_post_tick_callback(tick)

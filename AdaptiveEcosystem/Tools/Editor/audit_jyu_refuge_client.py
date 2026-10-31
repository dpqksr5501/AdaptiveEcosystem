"""Passive client join observation. Does not spawn actors, change policy or move the player."""
import json,re,time
from pathlib import Path
import unreal

cmd=unreal.SystemLibrary.get_command_line()
name=re.search(r'-RefugeClientName=(\w+)',cmd)
if not name:raise RuntimeError('Use -RefugeClientName=ClientA or ClientB')
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'RefugeSafety_20261016'
state={'start':time.monotonic(),'seen':None}
def tick(dt):
    # -game has no UnrealEditorSubsystem. Observe the existing game world.
    game=next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name()=='LV_JYU_RefugeSafety'),None)
    if not game:return
    refuges=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoRefugeHabitat)
    if not refuges:return
    if state['seen'] is None:state['seen']=time.monotonic()
    if time.monotonic()-state['seen']<6:return
    data=[{'ready':a.get_editor_property('registration_ready'),'brush':a.get_editor_property('brush').get_instance_count(),
        'rocks':a.get_editor_property('boulders').get_instance_count(),'visible':a.get_editor_property('brush').is_visible()} for a in refuges]
    result={'refuges':data,'count':len(data),'ready':sum(r['ready'] for r in data),'visible':sum(r['visible'] and r['brush']>50 and r['rocks']>8 for r in data)}
    result['passed']=result['count']==result['ready']==result['visible']==12
    (out/(name.group(1)+'_Refuges.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    unreal.log('JYU_REFUGE_CLIENT '+json.dumps(result))
    unreal.unregister_slate_post_tick_callback(handle)
handle=unreal.register_slate_post_tick_callback(tick)

"""Observe the saved refuge map and real creatures, then exit normally. No animal fixtures or policy writes."""
import json
import time
from collections import Counter
from pathlib import Path
import unreal

editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
world=editor.get_editor_world()
if 'LV_JYU_RefugeSafety' not in world.get_name():raise RuntimeError('Refuge copy only')
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('World Partition load failed')
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'RefugeSafety_20261016'
refuges=list(unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoRefugeHabitat))
if len(refuges)!=12:raise RuntimeError('Expected twelve authored refuge actors')
subject=next(a for a in refuges if 'Forest_0' in a.get_actor_label())
center=subject.get_actor_location()
view=center+unreal.Vector(-2000,-2000,1700)
editor.set_level_viewport_camera_info(view,unreal.MathLibrary.find_look_at_rotation(view,center+unreal.Vector(0,0,80)))
task=unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(out/'EditorRefuge.png'),delay=2)
state={'phase':'editor','deadline':time.monotonic()+240,'task':task,'samples':[],'next':0,'shot':0,'camera':None}

def capture(game,actor):
    key=actor.get_editor_property('visual_state').get_editor_property('stable_agent_id')
    raw=unreal.EcoCreatureInspectionLibrary.capture_agent(game,key)
    if isinstance(raw,tuple):raw=next((v for v in raw if isinstance(v,str)),None)
    if not raw:return None
    data=json.loads(raw)
    visual=actor.get_editor_property('visual_state')
    data['region']=str(visual.get_editor_property('region_id'))
    data['visual_speed_cm_s']=visual.get_editor_property('velocity').length()
    anim=actor.get_editor_property('creature_mesh').get_anim_instance()
    data['animation_pose']=anim.get_editor_property('animation_index') if anim else None
    return data

def finish(result):
    unreal.unregister_slate_post_tick_callback(handle)
    rows=[r for sample in state['samples'] for r in sample['deer']]
    wolves=[r for sample in state['samples'] for r in sample['wolves']]
    totals={}
    for row in rows+wolves:
        name=row['region'];s=totals.setdefault(name,{})
        for key in ('refuge_protected_prey_steps','refuge_constrained_moves','refuge_capture_violations','refuge_inside_predator_steps'):
            s[key]=max(s.get(key,0),row.get(key,0))
    game=editor.get_game_world()
    final_refuges=[{'position':str(a.get_actor_location()),'brush':a.get_editor_property('brush').get_instance_count(),
        'rocks':a.get_editor_property('boulders').get_instance_count(),'registration':a.get_editor_property('shelter_runtime_index'),
        'ready':a.get_editor_property('registration_ready'),'projected_slots':a.get_editor_property('project_slots_to_ground')}
        for a in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoRefugeHabitat)] if game else []
    summary={'result':result,'samples':len(state['samples']),'deer_records':len(rows),'wolf_records':len(wolves),
        'protected_records':sum(r.get('refuge_protected_here',False) for r in rows),
        'sitting_protected_records':sum(r.get('refuge_protected_here') and r.get('animation_pose')==3 for r in rows),
        'occupied_records':sum(r.get('shelter_state')==4 for r in rows),
        'wolf_inside_records':sum(r.get('wolf_inside_refuge',False) for r in wolves),
        'executed_counts':dict(Counter(r.get('executed') for r in rows)),
        'region_safety_counters':totals,
        'ready_refuges':sum(r['ready'] for r in final_refuges),'refuges':final_refuges}
    (out/'Runtime.json').write_text(json.dumps({'summary':summary,'samples':state['samples']},indent=2),encoding='utf-8')
    unreal.log('JYU_REFUGE_AUDIT_'+result+' '+json.dumps(summary))
    if state['camera']:state['camera'].destroy_actor()
    levels.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()

def tick(dt):
    try:
        now=time.monotonic()
        if now>state['deadline']:finish('TIMEOUT');return
        if state['phase']=='editor':
            if not state['task'].is_task_done():return
            levels.editor_request_begin_play();state['phase']='waiting';return
        game=editor.get_game_world()
        if not game or unreal.GameplayStatics.get_time_seconds(game)<1:return
        if state['phase']=='waiting':
            state['phase']='observe';state['start']=now
            player=unreal.GameplayStatics.get_player_controller(game,0)
            camera=unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(game,unreal.CameraActor,unreal.Transform(location=view))
            if not camera:raise RuntimeError('Read-only camera rejected')
            state['camera']=camera;player.set_view_target_with_blend(camera,0)
            state['refuges']=[{'position':str(a.get_actor_location()),'brush':a.get_editor_property('brush').get_instance_count(),
                'rocks':a.get_editor_property('boulders').get_instance_count(),'registration':a.get_editor_property('shelter_runtime_index'),
                'projected_slots':a.get_editor_property('project_slots_to_ground')} for a in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoRefugeHabitat)]
            for command in ('eco.Shelter.Log 1','eco.Social.ActionAudit 1'):unreal.SystemLibrary.execute_console_command(game,command)
        elapsed=now-state['start']
        if elapsed>=40:finish('FINISHED');return
        if elapsed<state['next']:return
        state['next']=elapsed+.5
        actors=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureRepresentationActor)
        deer=[];wolves=[];pairs=[]
        for actor in actors:
            if not actor.get_editor_property('bound') or not actor.get_editor_property('visual_state').get_editor_property('alive'):continue
            row=capture(game,actor)
            if not row:continue
            (wolves if row['species']=='Wolf' else deer).append(row)
            if row['species']=='Herbivore':pairs.append((actor,row))
        state['samples'].append({'elapsed':elapsed,'deer':deer,'wolves':wolves})
        protected=[(a,r) for a,r in pairs if r.get('refuge_protected_here') and r.get('animation_pose')==3]
        if protected:
            actor,row=protected[0]
            habitats=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoRefugeHabitat)
            habitat=min(habitats,key=lambda h:(h.get_actor_location()-actor.get_actor_location()).length())
            point=habitat.get_actor_location()+unreal.Vector(0,0,60)
            camera=state['camera']
            close=state['shot']>=1
            focus=actor.get_actor_location()+unreal.Vector(0,0,80) if close else point
            offset=unreal.Vector(-700,-1000,750) if close else unreal.Vector(-1800,-1800,1600)
            position=focus+offset
            camera.set_actor_location(position,False,False)
            camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(position,focus),False)
        elif state['shot']==0:
            state['camera'].set_actor_location(view,False,False)
            state['camera'].set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(view,center),False)
        threshold=12 if state['shot']==0 else 24
        if state['shot']<2 and elapsed>=threshold:
            name='RefugePIE.png' if state['shot']==0 else 'RefugeClose.png'
            unreal.SystemLibrary.execute_console_command(game,'HighResShot 1280x720 filename="'+str(out/name).replace(chr(92),'/')+'"')
            state['shot']+=1
    except Exception as error:
        unreal.log_error('JYU_REFUGE_AUDIT_ERROR '+repr(error));finish('FAILED')

handle=unreal.register_slate_post_tick_callback(tick)

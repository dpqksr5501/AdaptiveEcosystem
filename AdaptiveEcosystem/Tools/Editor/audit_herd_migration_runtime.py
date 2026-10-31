"""Observe a real copy-map runtime/PIE. One explicit receipted food-loss fixture; no agent teleport or policy writes."""
import json,math,re,time
from pathlib import Path
import unreal

cmd=unreal.SystemLibrary.get_command_line()
def arg(key,default):
    m=re.search(r'-'+key+r'=([^\s"]+)',cmd,re.I)
    return m.group(1) if m else default
name=arg('HerdAuditName','PIE')
duration=float(arg('HerdAuditDuration','120'))
pie='-HerdAuditPIE' in cmd
headless='-server' in cmd.lower()
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'HerdMigration_20261022'
out.mkdir(parents=True,exist_ok=True)
state={'samples':[],'start':None,'next':0,'loss':False,'camera':None,'shots':0,'refuge_shot':False,'last':{},'transfers':[], 'error':None}
deadline=time.monotonic()+duration+120
if pie:
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if 'LV_JYU_HerdMigration' not in editor.get_editor_world().get_name():raise RuntimeError('Owned migration copy only')
    if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(editor.get_editor_world()):raise RuntimeError('Partition load failed')
    levels.editor_request_begin_play()

def world():
    if pie:return editor.get_game_world()
    return next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name()=='LV_JYU_HerdMigration'),None)
def capture(game,key):
    raw=unreal.EcoCreatureInspectionLibrary.capture_agent(game,key)
    if isinstance(raw,tuple):raw=next((v for v in raw if isinstance(v,str)),None)
    return json.loads(raw) if raw else None
def finish(result):
    if headless:relay.on_runtime_sample.remove_callable(tick)
    else:unreal.unregister_slate_post_tick_callback(handle)
    rows=[r for s in state['samples'] for r in s['agents']]
    summary={'result':result,'name':name,'samples':len(state['samples']),'food_loss_fixture':state['loss'],'error':state['error'],
        'migration_samples':sum(r.get('migration_active',False) for r in rows),
        'plan_ids':sorted(set(r.get('migration_plan',0) for r in rows if r.get('migration_plan',0)>0)),
        'arrived_ids':sorted(set(r['stable_id'] for r in rows if r.get('migration_reason')=='Arrived')),
        'region_transfers':state['transfers'],'history_records':sum(len(r.get('reason_history',[])) for r in rows),
        'observation_wall_seconds':duration,'fixture':'Sustained Barren drought (receipted food loss and suspended regeneration), observers disabled; model weights unchanged'}
    (out/(name+'_Runtime.json')).write_text(json.dumps({'summary':summary,'samples':state['samples']},ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('HERD_RUNTIME_FINISHED '+json.dumps(summary))
    if pie:
        if state['camera']:state['camera'].destroy_actor()
        levels.editor_request_end_play();unreal.SystemLibrary.quit_editor()

def tick(dt):
    try:
        if time.monotonic()>deadline:
            state['error']='Runtime initialization/observation deadline';finish('FAILED');return
        game=world()
        if not game:return
        runtime=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureIntegrationSpawner)
        if not runtime or not runtime[0].is_runtime_ready():return
        now=time.monotonic()
        if state['start'] is None:
            state['start']=now
            # Explicit observer fixture; both native player observation and generic threat source are disabled.
            for pawn in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.Pawn):
                for cls in (unreal.EcoPlayerEcologyComponent,unreal.EcoThreatSourceComponent):
                    for c in pawn.get_components_by_class(cls):c.set_editor_property('threat_enabled',False)
        elapsed=now-state['start']
        if elapsed>=duration:finish('FINISHED');return
        if elapsed<state['next']:return
        state['next']=elapsed+2
        for pawn in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.Pawn):
            for cls in (unreal.EcoPlayerEcologyComponent,unreal.EcoThreatSourceComponent):
                for c in pawn.get_components_by_class(cls):c.set_editor_property('threat_enabled',False)
        keys=unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(game)
        if elapsed>3 and not state['loss']:
            migration=next((s for s in unreal.ObjectIterator(unreal.EcoHerdMigrationSubsystem) if s.get_outer()==game),None)
            if not migration:raise RuntimeError('Missing authoritative herd subsystem')
            state['loss']=migration.apply_food_fraction_for_audit('Barren',0,True)
            if not state['loss']:raise RuntimeError('Receipted food-loss fixture rejected')
        rows=[]
        for key in keys:
            row=capture(game,key)
            if not row:continue
            rows.append(row)
            old=state['last'].get(str(key))
            if old and old.get('region')!=row.get('region'):
                p=old.get('native_world_position');q=row.get('native_world_position')
                state['transfers'].append({'id':key,'from':old.get('region'),'to':row.get('region'),
                    'distance_cm':math.dist(p,q) if p and q else None,'sample_seconds':2})
            state['last'][str(key)]=row
        state['samples'].append({'elapsed':elapsed,'authority_agents':len(keys),'agents':rows})
        progress={'elapsed':elapsed,'food_loss_fixture':state['loss'],'agents':[
            {k:r.get(k) for k in ('stable_id','region','migration_plan','migration_active','migration_state','migration_reason','migration_waypoint','decision_reason')}
            for r in rows if r.get('species')=='Herbivore']}
        (out/(name+'_Progress.json')).write_text(json.dumps(progress,indent=2),encoding='utf-8')
        if pie:
            candidates=[r for r in rows if r.get('migration_active') and r.get('native_world_position')]
            if not candidates:candidates=[r for r in rows if r.get('region')=='Barren' and r.get('native_world_position')]
            if candidates:
                selected=candidates[0]
                members=[r for r in candidates if r.get('migration_plan')==selected.get('migration_plan')]
                p=[sum(r['native_world_position'][k] for r in members)/len(members) for k in range(3)]
                focus=unreal.Vector(*p)+unreal.Vector(0,0,70)
                if elapsed>95:
                    refuges=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoRefugeHabitat)
                    if refuges:focus=refuges[0].get_actor_location()+unreal.Vector(0,0,70)
                if state['camera'] is None:
                    state['camera']=unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(game,unreal.CameraActor,unreal.Transform(location=focus))
                    unreal.GameplayStatics.get_player_controller(game,0).set_view_target_with_blend(state['camera'],0)
                pos=focus+unreal.Vector(-1800,-2300,1600)
                state['camera'].set_actor_location(pos,False,False)
                state['camera'].set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(pos,focus),False)
            if state['shots']<3 and elapsed>15+state['shots']*30:
                path=str(out/('HerdPIE_'+str(state['shots'])+'.png')).replace('\\','/')
                unreal.SystemLibrary.execute_console_command(game,'HighResShot 1280x720 filename="'+path+'"')
                state['shots']+=1
            if elapsed>98 and not state['refuge_shot']:
                path=str(out/'HerdPIE_Refuge.png').replace('\\','/')
                unreal.SystemLibrary.execute_console_command(game,'HighResShot 1280x720 filename="'+path+'"')
                state['refuge_shot']=True
    except Exception as error:
        state['error']=repr(error);unreal.log_error('HERD_RUNTIME_ERROR '+repr(error));finish('FAILED')
if headless:
    game=world()
    relay=next(iter(unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureIntegrationSpawner)),None) if game else None
    if not relay:raise RuntimeError('Dedicated audit needs an existing runtime boundary relay')
    relay.on_runtime_sample.add_callable(tick)
else:handle=unreal.register_slate_post_tick_callback(tick)
unreal.log('HERD_RUNTIME_OBSERVER_BOUND '+('RuntimeBoundary' if headless else 'Slate'))

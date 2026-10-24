"""Capture actual PIE behavior with a camera, observer-threat fixture, and explicit drought.
Personal presentation output belongs outside the repository; pass -MigrationStoryOutput=<folder>.
"""
import json,math,re,time
from pathlib import Path
import unreal

cmd=unreal.SystemLibrary.get_command_line()
def arg(key,default):
    match=re.search(r'-'+key+r'=("[^"]*"|\S+)',cmd,re.I)
    return match.group(1).strip('"') if match else default
destination=arg('MigrationStoryOutput','')
if not destination:raise RuntimeError('Personal captures require an explicit external -MigrationStoryOutput folder')
out=Path(destination).resolve()
project=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
if out.is_relative_to(project.parent):raise RuntimeError('Personal presentation output must stay outside the repository')
out.mkdir(parents=True,exist_ok=True)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if 'LV_JYU_HerdMigration' not in editor.get_editor_world().get_name():raise RuntimeError('Owned migration map only')
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(editor.get_editor_world()):raise RuntimeError('Partition load failed')
state={'start':None,'next':0,'camera':None,'drought':False,'plan':0,'agent':None,'rest_plan':0,'shots':{},'pending':None,'snapshots':[],'error':None}
deadline=time.monotonic()+290
levels.editor_request_begin_play()

def read_snapshot(game):
    result=unreal.EcoCreatureInspectionLibrary.capture_migration(game)
    if isinstance(result,tuple):result=next((v for v in result if isinstance(v,str)),None)
    return json.loads(result) if result else None
def shot(game,name,focus,snapshot,plan=0,close=False):
    if name in state['shots'] or state['pending']:return
    camera=state['camera'];point=unreal.Vector(*focus)+unreal.Vector(0,0,80)
    offset=unreal.Vector(-1400,-1900,1300) if close else unreal.Vector(-8500,-10500,10500)
    position=point+offset;camera.set_actor_location(position,False,False)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(position,point),False)
    hud=unreal.GameplayStatics.get_player_controller(game,0).get_hud()
    if isinstance(hud,unreal.EcoCreatureInspectorHUD) and plan:hud.focus_migration_plan(plan)
    state['pending']={'name':name,'due':time.monotonic()+.45,'trigger':snapshot,'plan':plan}
def finish(result):
    unreal.unregister_slate_post_tick_callback(handle)
    summary={'result':result,'error':state['error'],'tracked_plan':state['plan'],'tracked_agent':state['agent'],
        'shots':state['shots'],'snapshots':state['snapshots'],
        'fixture':'Actual PIE. Explicit sustained Barren drought. Observer threats disabled. No creature relocation or policy writes.'}
    (out/'MigrationStory.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('MIGRATION_STORY_FINISHED '+result+' SHOTS='+','.join(state['shots']))
    levels.editor_request_end_play();unreal.SystemLibrary.quit_editor()

def tick(dt):
    try:
        if time.monotonic()>deadline:state['error']='Runtime deadline';finish('FAILED');return
        game=editor.get_game_world()
        if not game:return
        runtime=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureIntegrationSpawner)
        if not runtime or not runtime[0].is_runtime_ready():return
        now=time.monotonic()
        if state['start'] is None:
            state['start']=now
            for command in ('eco.V3Debug 0','eco.Creature.Labels 0','eco.HerdMigration.Debug 1','eco.Inspector.Visible 0'):
                unreal.SystemLibrary.execute_console_command(game,command)
            state['camera']=unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(game,unreal.CameraActor,unreal.Transform())
            unreal.GameplayStatics.get_player_controller(game,0).set_view_target_with_blend(state['camera'],0)
        elapsed=now-state['start']
        if elapsed>170:finish('FINISHED');return
        if elapsed<state['next']:return
        state['next']=elapsed+.5
        for pawn in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.Pawn):
            for cls in (unreal.EcoPlayerEcologyComponent,unreal.EcoThreatSourceComponent):
                for component in pawn.get_components_by_class(cls):component.set_editor_property('threat_enabled',False)
        snapshot=read_snapshot(game)
        if not snapshot:return
        if not state['snapshots'] or elapsed-state['snapshots'][-1]['elapsed']>2:
            state['snapshots'].append({'elapsed':elapsed,**snapshot})
            (out/'MigrationStory_Progress.json').write_text(json.dumps({'elapsed':elapsed,'plan':state['plan'],'agent':state['agent'],'shots':list(state['shots'])}),encoding='utf-8')
        if state['pending']:
            pending=state['pending']
            if now>=pending['due']:
                filename=pending['name']+'.png'
                unreal.SystemLibrary.execute_console_command(game,'HighResShot 1280x720 filename="'+str(out/filename).replace('\\','/')+'"')
                state['shots'][pending['name']]={'elapsed':elapsed,'plan':pending['plan'],'snapshot':snapshot}
                state['pending']=None
            return
        overview=[34000,25000,-1000]
        if elapsed>3 and '00_overview_before' not in state['shots']:
            shot(game,'00_overview_before',overview,snapshot);return
        if elapsed>8 and not state['drought']:
            migration=next(s for s in unreal.ObjectIterator(unreal.EcoHerdMigrationSubsystem) if s.get_outer()==game)
            state['drought']=migration.apply_food_fraction_for_audit('Barren',0,True)
            if not state['drought']:raise RuntimeError('Drought fixture rejected')
        if state['drought'] and elapsed>10 and '01_food_shortage' not in state['shots']:
            shot(game,'01_food_shortage',overview,snapshot);return
        plans=snapshot['plans'];members=snapshot['members']
        if not state['plan']:
            candidates=[p for p in plans if p['destination']=='Forest' and p['members']>=2]
            if candidates:
                chosen=sorted(candidates,key=lambda p:p['plan'])[0]
                state['plan']=chosen['plan']
                tracked=[m for m in members if m['plan']==state['plan']]
                state['agent']=tracked[0]['agent'] if tracked else None
        plan=next((p for p in plans if p['plan']==state['plan']),None)
        tracked=[m for m in members if m['plan']==state['plan']]
        member=next((m for m in tracked if m['agent']==state['agent']),None)
        if tracked:
            focus=[sum(m['position'][k] for m in tracked)/len(tracked) for k in range(3)]
            if elapsed>20 and '02_departure' not in state['shots']:
                shot(game,'02_departure',focus,snapshot,state['plan'],True);return
            if max(m['waypoint'] for m in tracked)>7 and '03_along_route' not in state['shots']:
                shot(game,'03_along_route',focus,snapshot,state['plan'],True);return
        if member and member['region']=='Barren':
            forest=next((r for r in snapshot['regions'] if r['region']=='Forest'),None)
            if forest and forest['minimum'][1]-member['position'][1]<2200 and member['position'][1]<forest['minimum'][1]:
                shot(game,'04_before_arrival',member['position'],snapshot,state['plan'],True)
                if state['pending']:return
        if member and member['region']=='Forest':
            shot(game,'05_after_arrival',member['position'],snapshot,state['plan'],True)
            if state['pending']:return
        if plan and plan['state']=='Settled' and member:
            shot(game,'06_settled',member['position'],snapshot,state['plan'],True)
            if state['pending']:return
        if elapsed>25 and '07_rest_or_regroup' not in state['shots']:
            p=next((p for p in plans if p['state']=='Resting'),None)
            if p:
                group=[m for m in members if m['plan']==p['plan']]
                if group:
                    state['rest_plan']=p['plan'];shot(game,'07_rest_or_regroup',group[0]['position'],snapshot,p['plan'],True);return
        if state['rest_plan'] and '07_rest_or_regroup' in state['shots'] and '09_after_rest' not in state['shots']:
            p=next((p for p in plans if p['plan']==state['rest_plan'] and p['state']=='Traveling'),None)
            old=state['shots']['07_rest_or_regroup']['snapshot']['members']
            group=[m for m in members if m['plan']==state['rest_plan'] and any(o['agent']==m['agent'] and math.dist(o['position'],m['position'])>50 for o in old)]
            if p and group:shot(game,'09_after_rest',group[0]['position'],snapshot,p['plan'],True);return
        if elapsed>130 and '08_refuge' not in state['shots']:
            refuges=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoRefugeHabitat)
            if refuges:
                refuge=sorted(refuges,key=lambda a:a.get_actor_label())[4]
                p=refuge.get_actor_location();shot(game,'08_refuge',[p.x,p.y,p.z],snapshot,state['plan'],True)
        if elapsed>50 and '10_blocked' not in state['shots']:
            p=next((p for p in plans if p['state']=='Blocked'),None)
            group=[m for m in members if p and m['plan']==p['plan'] and m['active']]
            if p and group:shot(game,'10_blocked',group[0]['position'],snapshot,p['plan'],True)
    except Exception as error:
        state['error']=repr(error);unreal.log_error('MIGRATION_STORY_ERROR '+repr(error));finish('FAILED')
handle=unreal.register_slate_post_tick_callback(tick)

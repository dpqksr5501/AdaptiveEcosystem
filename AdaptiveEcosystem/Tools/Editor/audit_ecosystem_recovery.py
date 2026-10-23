"""Explicit hunting/recovery fixture, using real strikes and the operation queue."""
import json,time,sys
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ecosystem_observation import capture_life,write_checkpoint_sample

world=next(w for w in unreal.ObjectIterator(unreal.World) if w.get_name()=='LV_JYU_Ecosystem' and unreal.GameplayStatics.get_game_state(w) is not None)
runtime=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoCreatureIntegrationSpawner)[0]
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'EcosystemLife_20261023'
out.mkdir(parents=True,exist_ok=True)
state=dict(start=None,queued=None,samples=[],error=None,requests=0,initial=[],target=None,next_pose=0)
deadline=time.monotonic()+160

def finish(result):
    checkpoint=None
    if result=='FINISHED':
        try:checkpoint=write_checkpoint_sample(world,runtime,out,'RecoveryRestart')
        except Exception as error:result='FAILED';state['error']=repr(error)
    runtime.on_runtime_sample.remove_callable(tick)
    unreal.unregister_slate_post_tick_callback(input_handle)
    (out/'Recovery.json').write_text(json.dumps(dict(result=result,error=state['error'],samples=state['samples'],checkpoint=checkpoint,
        initial_wolf_ids=state['initial'],strike_requests=state['requests'],
        fixture='Explicit player hunting with real TryStrike to empty Forest wolves, then queued authority recovery; not natural extinction or recovery'),indent=2),encoding='utf-8')
    unreal.log('ECOSYSTEM_RECOVERY_AUDIT_'+result)
    if '-ecosystemauditquitonfinish' in unreal.SystemLibrary.get_command_line().lower():unreal.SystemLibrary.execute_console_command(world,'QUIT')

def tick(dt):
    try:
        if time.monotonic()>deadline:raise RuntimeError('Recovery fixture deadline')
        if not runtime.is_runtime_ready():return
        row=capture_life(world)
        if not row['agents'] or any('life' not in a for a in row['agents']):return
        if state['start'] is None:state['start']=time.monotonic()
        elapsed=time.monotonic()-state['start']
        wolves=[a for a in row['agents'] if a['species']=='Wolf' and a['region']=='Forest' and a['hp']>0]
        if not state['initial']:
            if len(wolves)!=2:raise AssertionError('Explicit two-wolf fixture required')
            state['initial']=[a['stable_id'] for a in wolves]
        row['elapsed']=elapsed;state['samples'].append(row)
        if state['queued'] is None and wolves:
            if state['requests']>=32:raise AssertionError('Bounded real hunting did not empty the population')
            pawn=unreal.GameplayStatics.get_player_pawn(world,0)
            bridge=pawn.get_component_by_class(unreal.EcoPlayerEcologyComponent)
            if bridge is None:raise RuntimeError('Actual player strike bridge required')
            bridge.set_editor_property('use_keyboard_gait',False)
            state['target']=int(wolves[0]['stable_id']);state['next_pose']=0;aim_tick(0)
            bridge.try_strike();state['requests']+=1;return
        if state['queued'] is None:
            if not runtime.queue_population_recovery('Forest',True):raise AssertionError('Valid operation queue rejected')
            if runtime.queue_population_recovery('Forest',True):raise AssertionError('Duplicate pending recovery accepted')
            if runtime.queue_population_recovery('Unknown_Region',True):raise AssertionError('Unknown region accepted')
            state['queued']=elapsed;state['target']=None;return
        if elapsed-state['queued']<12:return
        if len(wolves)!=2 or any(a['stable_id'] in state['initial'] or a['life']['origin']!=2 or a['life']['generation']!=0 or a['life']['parent_a']!='0' or a['life']['parent_b']!='0' for a in wolves):
            raise AssertionError('Two real recovery founders and their origin/parentage were not observed')
        if runtime.queue_population_recovery('Forest',True):raise AssertionError('Recovery cooldown bypassed')
        for f in row['fields']:
            if abs(f['food']-f['ledger_amount'])>1e-5:raise AssertionError('Recovery changed resource accounting')
        finish('FINISHED')
    except Exception as error:
        state['error']=repr(error);unreal.log_error('RECOVERY_AUDIT_ERROR '+repr(error));finish('FAILED')
def aim_tick(dt):
    if state['target'] is None or time.monotonic()<state['next_pose']:return
    state['next_pose']=time.monotonic()+.1
    raw=unreal.EcoCreatureInspectionLibrary.capture_agent(world,state['target'])
    if isinstance(raw,tuple):raw=next((v for v in raw if isinstance(v,str)),None)
    if not raw:return
    agent=json.loads(raw)
    if agent.get('hp',0)<=0 or not agent.get('native_world_position'):return
    pawn=unreal.GameplayStatics.get_player_pawn(world,0)
    if pawn is None:return
    target=unreal.Vector(*agent['native_world_position'])
    ground=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,target+unreal.Vector(100,0,0))
    if isinstance(ground,tuple):ground=next((v for v in ground if isinstance(v,unreal.Vector)),None)
    if not isinstance(ground,unreal.Vector):return
    pawn.set_actor_location(ground+unreal.Vector(0,0,90),False,True)
    pawn.get_component_by_class(unreal.CharacterMovementComponent).stop_movement_immediately()
    rotation=unreal.MathLibrary.find_look_at_rotation(pawn.get_actor_location(),target+unreal.Vector(0,0,65))
    unreal.GameplayStatics.get_player_controller(world,0).set_control_rotation(rotation)
    pawn.set_actor_rotation(rotation,True)
input_handle=unreal.register_slate_post_tick_callback(aim_tick)
runtime.on_runtime_sample.add_callable(tick)

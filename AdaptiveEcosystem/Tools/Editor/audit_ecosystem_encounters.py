"""Explicit player fixtures through actual pawn movement/strike, never memory writes.

Same seed, wolves disabled for the three controlled trials. Teleporting only the
player keeps a chosen subject in an observed/rear approach; it is not natural play.
"""
import json,math,re,time,sys
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ecosystem_observation import write_checkpoint_sample

cmd=unreal.SystemLibrary.get_command_line()
def arg(key,default):
    m=re.search(r'-'+key+r'=([^\s\"]+)',cmd,re.I)
    return m.group(1) if m else default
mode=arg('EncounterTrial','harmless')
if mode not in ('harmless','ambush','chase'):raise RuntimeError('Explicit trial required')
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'EcosystemLife_20261023'
out.mkdir(parents=True,exist_ok=True)
world=next(w for w in unreal.ObjectIterator(unreal.World) if w.get_name()=='LV_JYU_Ecosystem' and unreal.GameplayStatics.get_game_state(w) is not None)
runtime=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoCreatureIntegrationSpawner)[0]
state=dict(start=None,next=0,move=0,strike=8,subject=None,rows=[],strikes=0,error=None,point=None)
deadline=time.monotonic()+150
def inspect(key):
    raw=unreal.EcoCreatureInspectionLibrary.capture_agent(world,key)
    if isinstance(raw,tuple):raw=next(v for v in raw if isinstance(v,str))
    return json.loads(raw)
def finish(result):
    checkpoint=None
    if result=='FINISHED':
        try:checkpoint=write_checkpoint_sample(world,runtime,out,'Encounter_'+mode)
        except Exception as error:state['error']=repr(error);result='FAILED'
    runtime.on_runtime_sample.remove_callable(tick)
    unreal.unregister_slate_post_tick_callback(input_handle)
    (out/('Encounter_'+mode+'.json')).write_text(json.dumps(dict(result=result,mode=mode,error=state['error'],subject=state['subject'],strike_groups=state['strikes'],strike_requests=state['strikes']*2,checkpoint=checkpoint,samples=state['rows'],fixture='Actual authority player repositioning; chase uses CharacterMovement; each damage group calls TryStrike twice to test rate limiting; no AI state writes'),indent=2),encoding='utf-8')
    unreal.log('ENCOUNTER_AUDIT_'+result+' '+mode)
    if '-ecosystemauditquitonfinish' in cmd.lower():unreal.SystemLibrary.execute_console_command(world,'QUIT')
def tick(dt):
    try:
        if time.monotonic()>deadline:raise RuntimeError('Fixture initialization deadline')
        if not runtime.is_runtime_ready():return
        pawn=unreal.GameplayStatics.get_player_pawn(world,0)
        if not isinstance(pawn,unreal.Character):raise RuntimeError('Actual player Character required')
        bridge=pawn.get_component_by_class(unreal.EcoPlayerEcologyComponent)
        if bridge is None:raise RuntimeError('Actual player ecology bridge required')
        bridge.set_editor_property('use_keyboard_gait',False)
        if state['subject'] is None:
            candidates=[inspect(k) for k in unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)]
            candidates=[a for a in candidates if a['species']=='Herbivore' and a['region']=='Forest' and a['hp']>0
                and a.get('native_world_position') and a.get('ecosystem_life_enabled') and 'native_head_x' in a]
            if not candidates:return
            state['subject']=int(min(candidates,key=lambda a:(a['native_world_position'][0]-34000)**2+(a['native_world_position'][1]-32000)**2)['stable_id']);state['start']=time.monotonic()
        elapsed=time.monotonic()-state['start']
        a=inspect(state['subject'])
        if a.get('hp',0)<=0:raise RuntimeError('Subject died before bounded trial finished')
        pos=unreal.Vector(*a['native_world_position'])
        state['point']=pos
        head=unreal.Vector(a['native_head_x'],a['native_head_y'],0)
        movement=pawn.get_component_by_class(unreal.CharacterMovementComponent)
        if movement is None:raise RuntimeError('Actual CharacterMovement component required')
        if elapsed>=state['move']:
            state['move']=elapsed+(0.1 if mode=='ambush' else 2 if mode=='harmless' else 4)
            distance=-150 if mode=='ambush' else 1600 if mode=='harmless' else 1800
            projected=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,pos+head*distance)
            if isinstance(projected,tuple):
                projected=None if any(isinstance(v,bool) and not v for v in projected) else next((v for v in projected if isinstance(v,unreal.Vector)),None)
            if isinstance(projected,unreal.Vector):
                pawn.set_actor_location(projected+unreal.Vector(0,0,100),False,True)
                if mode!='chase':movement.stop_movement_immediately()
        toward=pos-pawn.get_actor_location();length=math.hypot(toward.x,toward.y)
        pawn.set_actor_rotation(unreal.Rotator(0,math.degrees(math.atan2(toward.y,toward.x)),0),True)
        if mode=='chase':bridge.set_gait(unreal.EcoPlayerGait.RUN)
        if mode=='ambush' and elapsed>=state['strike'] and state['strikes']<3:
            bridge.try_strike();bridge.try_strike();state['strikes']+=1;state['strike']=elapsed+6
        if elapsed>=state['next']:
            state['next']=elapsed+1
            velocity=pawn.get_velocity()
            p=pawn.get_actor_location()
            state['rows'].append(dict(elapsed=elapsed,agent=a,player=[p.x,p.y,p.z],player_speed=math.hypot(velocity.x,velocity.y),distance=length,player_threat_enabled=bridge.get_editor_property('threat_enabled')))
        if elapsed>=55:
            rows=state['rows']
            if mode=='harmless':
                curious=[s for s in rows if s['agent']['life']['response']==1]
                if len(curious)<2 or max(s['agent']['life']['familiarity'] for s in rows)<=.12:raise AssertionError('Actual curiosity outcome was not observed')
                if min(s['distance'] for s in curious)<1100:raise AssertionError('Curiosity fixture violated the twelve-metre safety distance')
            elif mode=='ambush':
                if not 10<=min(s['agent']['hp'] for s in rows)<=70 or max(s['agent']['life']['unknown_fear'] for s in rows)<.15:raise AssertionError('Unknown-source damage or duplicate-strike rate limiting failed')
            elif max(s['player_speed'] for s in rows)<500 or not any(s['agent']['life']['last_encounter']==2 and s['agent']['life']['response']==3 for s in rows):
                raise AssertionError('Actual running pursuit and retreat were not observed')
            finish('FINISHED')
    except Exception as error:
        state['error']=repr(error);unreal.log_error('ENCOUNTER_AUDIT_ERROR '+repr(error));finish('FAILED')
def input_tick(dt):
    if mode!='chase' or state['point'] is None:return
    pawn=unreal.GameplayStatics.get_player_pawn(world,0)
    if pawn is None:return
    toward=state['point']-pawn.get_actor_location();distance=math.hypot(toward.x,toward.y)
    if distance>50:pawn.add_movement_input(unreal.Vector(toward.x/distance,toward.y/distance,0),1,False)
input_handle=unreal.register_slate_post_tick_callback(input_tick)
runtime.on_runtime_sample.add_callable(tick)

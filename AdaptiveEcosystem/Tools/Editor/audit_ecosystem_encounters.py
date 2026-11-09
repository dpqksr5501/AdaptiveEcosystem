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
follow_return=mode=='hunt' and '-encounterfollowreturn' in cmd.lower()
folder=arg('EncounterAuditFolder','EcosystemLife_20261023')
if mode not in ('harmless','ambush','chase','hunt') or not re.fullmatch(r'[A-Za-z0-9_]+',folder):
    raise RuntimeError('Explicit trial and simple output folder required')
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/folder
out.mkdir(parents=True,exist_ok=True)
world=next(w for w in unreal.ObjectIterator(unreal.World) if w.get_name()=='LV_JYU_Ecosystem' and unreal.GameplayStatics.get_game_state(w) is not None)
runtime=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoCreatureIntegrationSpawner)[0]
state=dict(start=None,next=0,move=0,strike=8,subject=None,rows=[],strikes=0,error=None,point=None)
deadline=time.monotonic()+150
def inspect(key):
    raw=unreal.EcoCreatureInspectionLibrary.capture_agent(world,key)
    if isinstance(raw,tuple):raw=next((v for v in raw if isinstance(v,str)),None)
    return json.loads(raw) if raw else {}
def finish(result):
    checkpoint=None
    if result=='FINISHED' and mode!='hunt':
        try:checkpoint=write_checkpoint_sample(world,runtime,out,'Encounter_'+mode)
        except Exception as error:state['error']=repr(error);result='FAILED'
    runtime.on_runtime_sample.remove_callable(tick)
    unreal.unregister_slate_post_tick_callback(input_handle)
    (out/('Encounter_'+mode+'.json')).write_text(json.dumps(dict(result=result,mode=mode,error=state['error'],subject=state['subject'],strike_groups=state['strikes'],strike_requests=state['strikes']*2,checkpoint=checkpoint,samples=state['rows'],return_observation=state.get('return'),fixture='Actual authority player repositioning; chase uses CharacterMovement; each damage group calls TryStrike twice to test rate limiting; no AI state writes'),indent=2),encoding='utf-8')
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
        now=unreal.GameplayStatics.get_time_seconds(world) if follow_return else time.monotonic()
        if state['subject'] is None:
            candidates=[inspect(k) for k in unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)]
            candidates=[a for a in candidates if a['species']=='Herbivore' and a['region']=='Forest' and a['hp']>0
                and a.get('native_world_position') and a.get('ecosystem_life_enabled') and 'native_head_x' in a]
            if not candidates:return
            state['subject']=int(min(candidates,key=lambda a:(a['native_world_position'][0]-34000)**2+(a['native_world_position'][1]-32000)**2)['stable_id']);state['start']=now
        elapsed=now-state['start']
        a=inspect(state['subject'])
        if follow_return and state.get('return'):
            observation=state['return']
            if a.get('hp',0)<=0:
                observation['end_reason']='subject_died_or_removed';finish('FINISHED');return
            x,y,_=a['native_world_position']
            distance=math.hypot(x-observation['center_cm'][0],y-observation['center_cm'][1])/100
            observation['distance_samples'].append(dict(seconds=elapsed,distance_m=distance,region=a['region']))
            if distance>18 and observation['departed_at'] is None:observation['departed_at']=elapsed
            if distance<=12 and observation['departed_at'] is not None and observation['returned_at'] is None:
                observation['returned_at']=elapsed
            if elapsed>=260:
                observation['end_reason']='observation_complete';finish('FINISHED')
            return
        if a.get('hp',0)<=0:raise RuntimeError('Subject died before bounded trial finished')
        pos=unreal.Vector(*a['native_world_position'])
        state['point']=pos
        head=unreal.Vector(a['native_head_x'],a['native_head_y'],0)
        movement=pawn.get_component_by_class(unreal.CharacterMovementComponent)
        if movement is None:raise RuntimeError('Actual CharacterMovement component required')
        if elapsed>=state['move']:
            state['move']=elapsed+(0.1 if mode in ('ambush','hunt') else 2 if mode=='harmless' else 4)
            distance={'ambush':-150,'hunt':150,'harmless':1600,'chase':1800}[mode]
            projected=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,pos+head*distance)
            if isinstance(projected,tuple):
                projected=None if any(isinstance(v,bool) and not v for v in projected) else next((v for v in projected if isinstance(v,unreal.Vector)),None)
            if isinstance(projected,unreal.Vector):
                pawn.set_actor_location(projected+unreal.Vector(0,0,100),False,True)
                if mode!='chase':movement.stop_movement_immediately()
        toward=pos-pawn.get_actor_location();length=math.hypot(toward.x,toward.y)
        pawn.set_actor_rotation(unreal.Rotator(yaw=math.degrees(math.atan2(toward.y,toward.x))),True)
        if mode=='chase':bridge.set_gait(unreal.EcoPlayerGait.RUN)
        strike_limit=2 if mode=='hunt' else 3
        if mode in ('ambush','hunt') and elapsed>=state['strike'] and state['strikes']<strike_limit:
            bridge.try_strike();bridge.try_strike();state['strikes']+=1;state['strike']=elapsed+(2 if mode=='hunt' else 6)
        if elapsed>=state['next']:
            state['next']=elapsed+1
            velocity=pawn.get_velocity()
            p=pawn.get_actor_location()
            state['rows'].append(dict(elapsed=elapsed,agent=a,player=[p.x,p.y,p.z],player_speed=math.hypot(velocity.x,velocity.y),distance=length,player_threat_enabled=bridge.get_editor_property('threat_enabled')))
        if elapsed>=(20 if mode=='hunt' else 55):
            rows=state['rows']
            if mode=='harmless':
                curious=[s for s in rows if s['agent']['life']['response']==1]
                if len(curious)<2 or max(s['agent']['life']['familiarity'] for s in rows)<=.12:raise AssertionError('Actual curiosity outcome was not observed')
                if min(s['distance'] for s in curious)<1100:raise AssertionError('Curiosity fixture violated the twelve-metre safety distance')
            elif mode=='ambush':
                if not 10<=min(s['agent']['hp'] for s in rows)<=70 or max(s['agent']['life']['unknown_fear'] for s in rows)<.15:raise AssertionError('Unknown-source damage or duplicate-strike rate limiting failed')
            elif mode=='hunt':
                life=[s['agent']['life'] for s in rows]
                evidence_times={l['hunt_time'] for l in life if l['hunt_time']>=0}
                if (min(s['agent']['hp'] for s in rows)>70 or not any(l['last_damage_attacker_known'] for l in life)
                        or len(evidence_times)<2 or max(l['hunt_pressure'] for l in life)<=.42):
                    raise AssertionError('A recognized strike and a second perceived hunt episode did not build pressure')
                if follow_return:
                    hunt=max(life,key=lambda l:l['hunt_time'])
                    # Native units are 200 cm. Move only the QA player away after the last strike.
                    center=[hunt['hunt_x']*200,hunt['hunt_y']*200]
                    state['return']=dict(center_cm=center,departed_at=None,returned_at=None,distance_samples=[])
                    for cls in (unreal.EcoPlayerEcologyComponent,unreal.EcoThreatSourceComponent):
                        for component in pawn.get_components_by_class(cls):
                            component.set_editor_property('threat_enabled',False)
                    pawn.set_actor_location(unreal.Vector(pos.x,pos.y,pos.z+12000),False,True)
                    return
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

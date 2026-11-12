"""Dedicated/two-client authority and actual configured-action RPC fixture."""
import json,time,re,traceback,math
from pathlib import Path
import unreal as u
cmd=u.SystemLibrary.get_command_line()
is_server='-huntingnetworkserver' in cmd.lower()
match=re.search(r'-HuntingNetworkClient=(\w+)',cmd)
name='Server' if is_server else match.group(1)
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'PlayerHunting_20261105/Network'
out.mkdir(parents=True,exist_ok=True)
state=dict(start=None,world=None,next=0,samples=[],events=[],bound=False,next_attack=0,sent=set(),deadline=time.monotonic()+150,finished=False,target=None,attack_inputs=0)
action=u.load_asset('/Game/Variant_Combat/Input/Actions/IA_ComboAttack')
data=u.load_asset('/Game/JWJ/Gameplay/DA_EcoUnarmedCombo')
montage=data.get_editor_property('montage')
lengths=[u.load_asset('/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_0'+str(i)).get_play_length() for i in (1,2,3)]
def event(value):
    state['events'].append(dict(result=str(value.result),id=str(value.target_stable_agent_id),damage=value.applied_damage,step=value.step_id,execution=value.attack_execution_id))
def finish(ok,error=None):
    if state['finished']:return
    state['finished']=True
    (out/(name+'.json')).write_text(json.dumps(dict(result='PASS' if ok else 'FAIL',error=error,samples=state['samples'],events=state['events'],
        attack_inputs=state['attack_inputs'],fixture='Authority player placement; Enhanced Input and GAS RPC; no HP/animal writes'),indent=2),encoding='utf-8')
    u.log('HUNTING_NETWORK_'+name+'_'+('PASS' if ok else 'FAIL'))
    if state['world']:u.SystemLibrary.execute_console_command(state['world'],'QUIT')
    else:u.SystemLibrary.quit_editor()
def inspect(world,key):
    raw=u.EcoCreatureInspectionLibrary.capture_agent(world,key)
    if isinstance(raw,tuple):raw=next((v for v in raw if isinstance(v,str)),None)
    return json.loads(raw) if raw else {}
def tick(dt):
    try:
        if time.monotonic()>state['deadline']:raise AssertionError('Network audit timeout')
        world=next((w for w in u.ObjectIterator(u.World) if w.get_name()=='1102_Integration_JWJ' and u.GameplayStatics.get_game_state(w)
                    and (is_server or u.GameplayStatics.get_player_controller(w,0))),None)
        state['world']=world
        if not world:return
        runtimes=u.GameplayStatics.get_all_actors_of_class(world,u.EcoCreatureIntegrationSpawner)
        if not runtimes or not runtimes[0].is_runtime_ready():return
        runtime=runtimes[0]
        pcs=[pc for pc in u.GameplayStatics.get_all_actors_of_class(world,u.PlayerController) if pc.get_controlled_pawn()]
        if not pcs and state['start'] is None:return
        now=time.monotonic()
        if state['start'] is None:state['start']=now
        elapsed=now-state['start']
        if is_server:
            if state['target'] is None:
                candidates=[inspect(world,key) for key in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)]
                state['target']=next((int(a['stable_id']) for a in candidates if a.get('species')=='Wolf' and a.get('region')=='JWJ_WildlifeTest' and a.get('hp',0)>0),None)
            animal=inspect(world,state['target']) if state['target'] else {}
            health_phase=runtime.get_combat_diagnostics().hunting_deaths>0
            if health_phase:
                if not state.get('alt'):
                    candidates=[inspect(world,key) for key in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)]
                    state['alt']=next((int(a['stable_id']) for a in candidates if a.get('species')=='Wolf' and a.get('region')=='JWJ_WildlifeTest' and a.get('hp',0)>0),None)
                animal=inspect(world,state['alt']) if state.get('alt') else {}
            for index,pc in enumerate(pcs):
                pawn=pc.get_controlled_pawn()
                if not animal.get('native_world_position') or animal.get('hp',0)<=0:continue
                pawn.get_editor_property('player_state').set_invulnerable(not health_phase)
                # Only A is placed in contact range; B observes the same death and late-join summary.
                offset=(u.Vector(140*math.cos(elapsed*.5),140*math.sin(elapsed*.5),96) if health_phase else u.Vector(-60,0,96)) if index==0 else u.Vector(-1500,0,96)
                pawn.set_actor_location(u.Vector(*animal['native_world_position'])+offset,False,True)
                pawn.character_movement.stop_movement_immediately();pawn.set_actor_rotation(u.Rotator(0,0,0),True)
                pc.set_control_rotation(u.Rotator(0,0,0))
        else:
            pc=u.GameplayStatics.get_player_controller(world,0);pawn=pc.get_controlled_pawn()
            if not pawn:return
            hit=pawn.get_component_by_class(u.EcoMeleeHitComponent)
            if not state['bound']:hit.on_damage_outcome.add_callable(event);state['bound']=True
            anim=pawn.mesh.get_anim_instance()
            subsystem=next((s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
                            if isinstance(s.get_outer(),u.LocalPlayer)),None)
            if not anim or not subsystem:return
            def press():
                subsystem.inject_input_vector_for_action(action,u.Vector(1,0,0),[],[])
                state['attack_inputs']+=1
            if name=='ClientA' and not any('DEATH_COMMITTED' in e['result'] for e in state['events']):
                if not anim.montage_is_playing(montage) and elapsed>=state['next_attack']:
                    press();state['next_attack']=elapsed+2;state['sent'].clear()
                if anim.montage_is_playing(montage):
                    index={'LeftPunch':0,'RightPunch':1,'Kick':2}.get(str(anim.montage_get_current_section(montage)),2)
                    fraction=(anim.montage_get_position(montage)-sum(lengths[:index]))/lengths[index]
                    if index<2 and .43<fraction<.64 and index not in state['sent']:press();state['sent'].add(index)
        if elapsed>=state['next']:
            state['next']=elapsed+1
            ids=u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)
            proxies=u.GameplayStatics.get_all_actors_of_class(world,u.EcoCreatureHitProxy)
            summary=u.GameplayStatics.get_game_state(world).get_ecology_summary()
            visuals=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.EcoCreatureRepresentationActor) if a.get_editor_property('bound')]
            state['samples'].append(dict(elapsed=elapsed,players=len(pcs),authority_agents=len(ids),hit_proxies=len(proxies),visuals=len(visuals),
                hunting_deaths=runtime.get_combat_diagnostics().hunting_deaths,player_hits=runtime.get_combat_diagnostics().player_hits,
                local_hp=u.GameplayStatics.get_player_pawn(world,0).get_editor_property('player_state').get_health() if not is_server else None,
                species=[dict(region=str(s.region_id),species=str(s.species_id),population=s.population,deaths=s.deaths) for s in summary.species]))
        if elapsed>=(80 if is_server else 60):
            if is_server:
                assert max(s['players'] for s in state['samples'])>=2,'Two real connections required'
                assert runtime.get_combat_diagnostics().hunting_deaths==1,'One server hunting death required'
                assert runtime.get_combat_diagnostics().player_hits>0,'Wolf damage to remote player required'
            else:
                assert all(s['authority_agents']==0 and s['hit_proxies']==0 for s in state['samples']),'Client executed logical authority or server collision'
                assert max(s['visuals'] for s in state['samples'])>0,'Received animal presentation required'
                assert any(any(r['deaths']>0 for r in s['species'] if r['region']=='JWJ_WildlifeTest' and r['species']=='Wolf') for s in state['samples']),'Committed species death summary missing'
                if name=='ClientA':
                    assert state['attack_inputs']>0,'Configured attack input not injected'
                    assert any('DEATH_COMMITTED' in e['result'] for e in state['events']),'Owner damage outcome RPC missing'
                    assert any(s.get('local_hp',100)<100 for s in state['samples']),'Replicated owner HP never changed'
            finish(True)
    except Exception:finish(False,traceback.format_exc())
def ticker(dt):
    # Synchronous engine calls can pump the ticker again.
    if state['finished'] or state.get('in_tick'):return not state['finished']
    state['in_tick']=True
    try:tick(dt)
    finally:state['in_tick']=False
    return not state['finished']

handle=u.register_ticker_callback(ticker,0.0)

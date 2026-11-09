"""Actual PIE input -> socket sweep -> identity damage -> existing ecology death.

Only the player is repositioned as an explicit fixture. Animals/food/HP are never
rewritten. Original maps/assets are not saved by this verification.
"""
import json, math, time, traceback
from pathlib import Path
import unreal as u

MAP='/Game/JWJ/1102_Integration_JWJ'
SPECIES='Herbivore' if '-huntingspecies=herbivore' in u.SystemLibrary.get_command_line().lower() else 'Wolf'
editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
if not levels.load_level(MAP): raise RuntimeError('Existing current level required')
data=u.load_asset('/Game/JWJ/Gameplay/DA_EcoUnarmedCombo')
action=u.load_asset('/Game/Variant_Combat/Input/Actions/IA_ComboAttack')
montage=data.get_editor_property('montage')
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'PlayerHunting_20261105'
out.mkdir(parents=True,exist_ok=True)
state=dict(deadline=time.monotonic()+150,phase='init',target=None,events=[],samples=[],started=None,
           next_attack=0,attack_started=None,sent=set(),next_sample=0,error=None,finished=False)
levels.editor_request_begin_play()

def inspect(world,key):
    value=u.EcoCreatureInspectionLibrary.capture_agent(world,key)
    if isinstance(value,tuple): value=next((v for v in value if isinstance(v,str)),None)
    return json.loads(value) if value else {}

def event(value):
    state['events'].append(dict(result=str(value.result),target=str(value.target_stable_agent_id),
                                execution=value.attack_execution_id,step=value.step_id,
                                applied=value.applied_damage,hp=value.remaining_hp,queue=value.queue_seconds))

def finish(ok):
    if state['finished']:return
    state['finished']=True
    report=dict(result='PASS' if ok else 'FAIL',error=state['error'],target=state['target'],events=state['events'],samples=state['samples'],
                fixture='Authority player repositioning and Enhanced Input; no animal/HP/food writes; no map save')
    (out/('PIE_Hunting_'+SPECIES+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    u.log('PLAYER_HUNTING_PIE_'+report['result'])
    u.unregister_slate_post_tick_callback(handle)
    levels.editor_request_end_play()
    u.SystemLibrary.quit_editor()

def tick(dt):
    try:
        if time.monotonic()>state['deadline']:raise AssertionError('Timed out at '+state['phase'])
        world=editor.get_game_world()
        if not world:return
        runtimes=u.GameplayStatics.get_all_actors_of_class(world,u.EcoCreatureIntegrationSpawner)
        if not runtimes or not runtimes[0].is_runtime_ready():return
        runtime=runtimes[0]
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn:return
        player=pawn.get_editor_property('player_state')
        if not isinstance(player,u.EcoPlayerState):raise AssertionError('Common GAS PlayerState missing')
        hit=pawn.get_component_by_class(u.EcoMeleeHitComponent)
        if not hit or hit.get_editor_property('attack_data') is None:raise AssertionError('Actual combo data missing')
        now=u.GameplayStatics.get_time_seconds(world)
        if state['phase']=='init':
            ids=u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)
            candidates=[inspect(world,key) for key in ids]
            candidates=[a for a in candidates if a.get('species')==SPECIES and a.get('hp',0)>0 and a.get('native_world_position')]
            if not candidates:return
            state['target']=int(candidates[0]['stable_id']);state['started']=now
            state['initial_hp']=candidates[0]['hp'];state['phase']='hunting'
            hit.on_damage_outcome.add_callable(event)
            player.set_invulnerable(True)
            state['initial_deaths']=runtime.get_combat_diagnostics().hunting_deaths
        animal=inspect(world,state['target'])
        if state['phase']=='hunting':
            if animal.get('hp',0)<=0:
                state['phase']='death';state['death_at']=now
            else:
                ground=u.Vector(*animal['native_world_position'])
                # Put the player's forward melee arc on the live body, without moving the animal.
                pawn.set_actor_location(ground+u.Vector(-60,0,96),False,True)
                pawn.character_movement.stop_movement_immediately()
                pawn.set_actor_rotation(u.Rotator(0,0,0),True)
                pawn.get_controller().set_control_rotation(u.Rotator(0,0,0))
                subsystem=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer))
                anim=pawn.mesh.get_anim_instance()
                def press():subsystem.inject_input_vector_for_action(action,u.Vector(1,0,0),[],[])
                if not anim.montage_is_playing(montage) and now>=state['next_attack']:
                    press();state['next_attack']=now+2;state['sent'].clear()
                if anim.montage_is_playing(montage):
                    section=str(anim.montage_get_current_section(montage))
                    index={'LeftPunch':0,'RightPunch':1,'Kick':2}.get(section,2)
                    sequence=u.load_asset('/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_0'+str(index+1))
                    lengths=[u.load_asset('/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_0'+str(i)).get_play_length() for i in (1,2,3)]
                    fraction=(anim.montage_get_position(montage)-sum(lengths[:index]))/lengths[index]
                    if index<2 and .45<fraction<.6 and index not in state['sent']:
                        press();state['sent'].add(index)
        if now>=state['next_sample']:
            state['next_sample']=now+1
            stats=runtime.get_combat_diagnostics()
            proxies=u.GameplayStatics.get_all_actors_of_class(world,u.EcoCreatureHitProxy)
            target_proxy=next((p for p in proxies if p.get_editor_property('stable_agent_id')==state['target']),None)
            extra=dict(pawn=str(pawn.get_actor_location()),sockets={k:str(pawn.mesh.get_socket_location(k)) for k in ['Attack_Hand_L','Attack_Hand_R','Attack_Foot','foot_r','foot_l']},
                       active_step=hit.get_editor_property('active_step'),contacts=hit.get_editor_property('contact_count'),target_native=animal.get('native_world_position'))
            if target_proxy:
                extra['proxy']=str(target_proxy.get_actor_location())
                extra['proxy_radius']=target_proxy.shape.get_scaled_capsule_radius()
                extra['proxy_height']=target_proxy.shape.get_scaled_capsule_half_height()
                extra['proxy_query']=str(u.SystemLibrary.sphere_trace_multi_for_objects(world,target_proxy.get_actor_location(),target_proxy.get_actor_location(),14,[u.ObjectTypeQuery.OBJECT_TYPE_QUERY2],False,[pawn],u.DrawDebugTrace.NONE,True))
            state['samples'].append(dict(time=now,phase=state['phase'],hp=animal.get('hp'),player_hp=player.get_health(),extra=extra,
               proxies=stats.active_proxies,queued=stats.contacts_queued,commits=stats.damage_committed,deaths=stats.hunting_deaths,max_queue=stats.maximum_queue_seconds))
            (out/'PIE_Live.json').write_text(json.dumps(dict(phase=state['phase'],samples=state['samples'][-4:],events=state['events']),indent=2),encoding='utf-8')
        if state['phase']=='hunting' and now-state['started']>16 and not state['events']:raise AssertionError('No logical contact; inspect PIE_Live.json')
        if state['phase']=='death' and now-state['death_at']>3:
            stats=runtime.get_combat_diagnostics()
            assert stats.hunting_deaths==state['initial_deaths']+1,'Exactly one hunting death required'
            commits=[e for e in state['events'] if 'COMMITTED' in e['result'] and 'DEATH' not in e['result']]
            assert commits and all(int(e['target'])==state['target'] for e in commits),'Wrong logical target'
            assert abs(sum(e['applied'] for e in commits)-state['initial_hp'])<.01,'Actual damage must sum to original HP'
            assert any('DEATH_COMMITTED' in e['result'] for e in state['events']),'No confirmed death outcome'
            assert len({(e['execution'],e['step'],e['target']) for e in commits})==len(commits),'Duplicate stage damage'
            assert any(e['step']>0 for e in commits),'Combo did not advance'
            finish(True)
    except Exception:
        state['error']=traceback.format_exc();u.log_error(state['error']);finish(False)
handle=u.register_slate_post_tick_callback(tick)

"""Paired, seeded existing-level runs. Real attacks only; drought is a named separate fixture."""
import json,re,time,sys,traceback
from pathlib import Path
import unreal as u
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ecosystem_observation import capture_life,write_checkpoint_sample,checkpoint_digest
cmd=u.SystemLibrary.get_command_line()
def arg(key,default):
    match=re.search('-'+key+r'=([^\s\"]+)',cmd,re.I)
    return match.group(1) if match else default
MODE=arg('HuntingAudit','baseline')
if MODE not in ['baseline','hunt','drought','save','load']:raise RuntimeError('Explicit audit mode required')
DURATION=float(arg('HuntingSeconds','1800'))
SEED=int(arg('EcoV3Seed','23'))
NAME=MODE+'_'+str(SEED)
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'PlayerHunting_20261105'
out.mkdir(parents=True,exist_ok=True)
world=next(w for w in u.ObjectIterator(u.World) if w.get_name()=='1102_Integration_JWJ' and u.GameplayStatics.get_game_state(w))
runtime=u.GameplayStatics.get_all_actors_of_class(world,u.EcoCreatureIntegrationSpawner)[0]
state=dict(start=None,first=None,next=0,samples=[],events=[],target=None,initial_wolves=[],sent=set(),next_attack=0,
           deadline=time.monotonic()+900,finished=False,operation=None)
data=u.load_asset('/Game/JWJ/Gameplay/DA_EcoUnarmedCombo')
montage=data.get_editor_property('montage')
action=u.load_asset('/Game/Variant_Combat/Input/Actions/IA_ComboAttack')
lengths=[u.load_asset('/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_0'+str(i)).get_play_length() for i in (1,2,3)]

def migration():
    value=u.EcoCreatureInspectionLibrary.capture_migration(world)
    if isinstance(value,tuple):value=next((v for v in value if isinstance(v,str)),None)
    return json.loads(value) if value else {}
def event(value):
    state['events'].append(dict(result=str(value.result),target=str(value.target_stable_agent_id),step=value.step_id,execution=value.attack_execution_id,applied=value.applied_damage))
def snapshot(row,elapsed):
    living=[a for a in row['agents'] if a.get('hp',0)>0]
    counts={}
    for a in living:
        key=a['region']+':'+a['species'];counts[key]=counts.get(key,0)+1
    summary=u.GameplayStatics.get_game_state(world).get_ecology_summary()
    regions=[dict(id=str(r.region_id),population=r.population,external_deaths=r.external_deaths,starvation=r.starvation_deaths,
                  migration_in=r.migration_in_count,migration_out=r.migration_out_count,predation_history=r.predation_history) for r in summary.regions]
    return dict(simulation_seconds=elapsed,counts=counts,regions=regions,fields=row['fields'],migration=migration(),
                natural_children=[a['stable_id'] for a in row['agents'] if a.get('life',{}).get('origin')==1],
                combat_deaths=runtime.get_combat_diagnostics().hunting_deaths,
                agents=[{k:a[k] for k in ['stable_id','species','region','hp','energy','native_world_position','life'] if k in a} for a in row['agents']])
def finish(ok,error=None):
    if state['finished']:return
    state['finished']=True
    report=dict(result='PASS' if ok else 'FAIL',mode=MODE,seed=SEED,error=error,samples=state['samples'],events=state['events'],operation=state['operation'],
                initial_wolves=state['initial_wolves'],duration_simulation_seconds=DURATION,
                fixture='Explicit food removal with regeneration suspended' if MODE=='drought' else 'Actual player input hunting' if MODE=='hunt' else 'No intervention' if MODE=='baseline' else 'Explicit checkpoint operation')
    (out/('Loop_'+NAME+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    u.log('HUNTING_LOOP_'+report['result']+' '+NAME)
    runtime.on_runtime_sample.remove_callable(tick)
    u.unregister_slate_post_tick_callback(input_handle)
    u.SystemLibrary.execute_console_command(world,'QUIT')
def tick(dt):
    try:
        if time.monotonic()>state['deadline']:raise AssertionError('Audit deadline')
        if not runtime.is_runtime_ready():return
        row=capture_life(world)
        if len(row['fields'])!=2 or any('native_step' not in f for f in row['fields']):return
        if state['first'] is None:
            state['first']=row['fields'][0]['native_step'];state['start']=time.monotonic()
            state['initial_wolves']=[a['stable_id'] for a in row['agents'] if a['species']=='Wolf' and a['region']=='JWJ_WildlifeTest' and a['hp']>0]
            pawn=u.GameplayStatics.get_player_pawn(world,0)
            if MODE=='hunt':pawn.get_component_by_class(u.EcoMeleeHitComponent).on_damage_outcome.add_callable(event)
            if MODE=='drought':
                subsystem=next(m for m in u.ObjectIterator(u.EcoHerdMigrationSubsystem) if m.get_outer()==world)
                assert subsystem.apply_food_fraction_for_audit('JWJ_WildlifeTest',0,True),'Drought transaction rejected'
            if MODE=='load':
                assert runtime.load_ecosystem('HuntingRestart'),'Checkpoint restore rejected'
                row=capture_life(world);state['first']=row['fields'][0]['native_step']
                expected=json.loads((out/'HuntingRestart_Expected.json').read_text(encoding='utf-8'))
                assert checkpoint_digest(row)==expected,'Restored agents/resources differ from saved snapshot'
                assert runtime.get_combat_diagnostics().pending_damage==0,'Transient combat survived checkpoint restore'
                state['operation']=dict(restored=True,exact_digest_match=True,pending_damage=0)
        elapsed=(row['fields'][0]['native_step']-state['first'])*2/15
        for f in row['fields']:
            for a,b in [('food','ledger_amount'),('consumed','ledger_consumed'),('grown','ledger_grown'),('environment_lost','ledger_environment_lost')]:
                assert abs(f[a]-f[b])<1.e-5,'Food conservation mismatch '+a
        if MODE=='save' and elapsed>=30 and state['operation'] is None:
            if runtime.save_ecosystem('HuntingRestart'):
                state['operation']=write_checkpoint_sample(world,runtime,out,'HuntingRestart')
        if elapsed>=state['next']:
            state['next']=elapsed+10
            state['samples'].append(snapshot(row,elapsed))
            (out/('Loop_'+NAME+'_Progress.json')).write_text(json.dumps(state['samples'][-1],indent=2),encoding='utf-8')
        if MODE=='hunt' and elapsed>25 and not state['events']:raise AssertionError('Configured combat action did not produce a contact; inspect InputDiagnostics.json')
        if elapsed>=DURATION:
            if MODE=='hunt':assert runtime.get_combat_diagnostics().hunting_deaths>=len(state['initial_wolves']),'Source wolves not hunted through actual combat'
            if MODE=='drought':
                sample=state['samples'][-1]
                assert any(r['id']=='JWJ_WildlifeTest' and r['migration_out']>0 for r in sample['regions']),'No committed departure from depleted region'
                assert any(r['id']=='JWJ_HuntingMeadow' and r['migration_in']>0 for r in sample['regions']),'No committed arrival at destination'
                initial_ids={a['stable_id'] for a in state['samples'][0]['agents'] if a['region']=='JWJ_WildlifeTest' and a['species']=='Herbivore'}
                assert any(a['stable_id'] in initial_ids and a['region']=='JWJ_HuntingMeadow' and a['hp']>0 for a in sample['agents']),'Actual native agents did not transfer region'
            if MODE in ['save','load']:assert state['operation'],'Checkpoint did not complete'
            finish(True)
    except Exception:finish(False,traceback.format_exc())
def input_tick(dt):
    if not runtime.is_runtime_ready() or state['finished']:return
    try:
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn:return
        if MODE!='hunt' or state['first'] is None:
            pawn.set_actor_location(u.Vector(0,-45000,4200),False,True)
            pawn.character_movement.stop_movement_immediately();return
        pawn.get_editor_property('player_state').set_invulnerable(True)
        if state['target'] is None:
            dead={e['target'] for e in state['events'] if 'DEATH_COMMITTED' in e['result']}
            state['target']=next((key for key in state['initial_wolves'] if str(key) not in dead),None)
        if state['target'] is None:
            pawn.set_actor_location(u.Vector(0,-45000,4200),False,True);return
        raw=u.EcoCreatureInspectionLibrary.capture_agent(world,int(state['target']))
        if isinstance(raw,tuple):raw=next((v for v in raw if isinstance(v,str)),None)
        a=json.loads(raw) if raw else {}
        if a.get('hp',0)<=0:state['target']=None;return
        point=u.Vector(*a['native_world_position'])
        pawn.set_actor_location(point+u.Vector(-60,0,96),False,True);pawn.character_movement.stop_movement_immediately()
        pawn.set_actor_rotation(u.Rotator(0,0,0),True)
        avatar=pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
        if 'input_diagnostics' not in state:
            asc=pawn.get_editor_property('player_state').get_editor_property('AbilitySystem')
            config=avatar.get_editor_property('InputConfig')
            state['input_diagnostics']=dict(pawn=pawn.get_path_name(),local=pawn.is_locally_controlled(),
                config=str(config),components=[str(c) for c in pawn.get_editor_property('player_state').get_components_by_class(u.AbilitySystemComponent)],bindings=[dict(action=str(b.get_editor_property('Action')),ability=str(b.get_editor_property('Ability'))) for b in config.get_editor_property('AbilityInputs')] if config else None,
                abilities=str(asc.get_all_abilities()) if asc else None)
            (out/'InputDiagnostics.json').write_text(json.dumps(state['input_diagnostics'],indent=2))

        avatar.release_configured_action(action)
        def press():avatar.press_configured_action(action)
        now=u.GameplayStatics.get_time_seconds(world);anim=pawn.mesh.get_anim_instance()
        if not anim.montage_is_playing(montage) and now>=state['next_attack']:
            press();state['next_attack']=now+2;state['sent'].clear()
        if anim.montage_is_playing(montage):
            index={'LeftPunch':0,'RightPunch':1,'Kick':2}.get(str(anim.montage_get_current_section(montage)),2)
            fraction=(anim.montage_get_position(montage)-sum(lengths[:index]))/lengths[index]
            if index<2 and .43<fraction<.64 and index not in state['sent']:press();state['sent'].add(index)
    except Exception:finish(False,traceback.format_exc())
runtime.on_runtime_sample.add_callable(tick)
input_handle=u.register_slate_post_tick_callback(input_tick)

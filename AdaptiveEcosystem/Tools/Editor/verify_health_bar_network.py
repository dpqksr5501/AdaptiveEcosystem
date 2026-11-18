"""Two owning clients shoot the same creature; both consume the shared HP display.

Fixture moves players on authority only and shares the server target point for aiming.
Damage uses existing rifle input/RPCs (including all normal server validation).
It never changes creature HP, replication payloads or health bar values.
"""
import json
import re
import time
import traceback
from pathlib import Path
import unreal as u

cmd = u.SystemLibrary.get_command_line()
server = '-HealthBarServer' in cmd
name = 'Server' if server else re.search(r'-HealthBarClient=(\w+)', cmd).group(1)
run_id = re.search(r'-HealthBarRun=(\w+)', cmd).group(1)
out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / 'HealthBarValidation/Network'
out.mkdir(parents=True, exist_ok=True)
state = dict(world=None, deadline=time.monotonic()+155, events=[], samples=[], next_sample=0, next_shot=0, shots=0)
aim = u.load_asset('/Game/JWJ/Weapons/IA_AimRifle')
fire = u.load_asset('/Game/JWJ/Weapons/IA_FireRifle')

def inspect(world, key):
    raw = u.EcoCreatureInspectionLibrary.capture_agent(world, key)
    if isinstance(raw, tuple):
        raw = next(v for v in raw if isinstance(v, str))
    return json.loads(raw) if raw else {}

def outcome(value):
    state['events'].append(dict(result=str(value.result), damage=value.applied_damage, id=int(value.target_stable_agent_id)))

def finish(ok, error=''):
    state['done'] = True
    (out/(name+'.json')).write_text(json.dumps(dict(run_id=run_id, result='PASS' if ok else 'FAIL', error=error,
        samples=state['samples'], events=state['events'], input_shots=state['shots']), indent=2), encoding='utf-8')
    u.log('[EcoHealthBar] '+name+' '+('PASS' if ok else 'FAIL '+error))
    world = state['world'] or next((w for w in u.ObjectIterator(u.World) if u.GameplayStatics.get_player_controller(w, 0)), None)
    if world:
        u.SystemLibrary.execute_console_command(world, 'QUIT')

def tick(dt):
    try:
        assert time.monotonic() < state['deadline'], 'Network fixture timeout'
        world = next((w for w in u.ObjectIterator(u.World) if w.get_name() == '1102_Integration_JWJ'
            and u.GameplayStatics.get_game_state(w) and (server or u.GameplayStatics.get_player_controller(w, 0))), None)
        state['world'] = world
        if not world:
            return
        if not state.get('logging'):
            state['logging'] = True
            u.SystemLibrary.execute_console_command(world, 'Log LogTemp Verbose')
        runtimes = u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureIntegrationSpawner)
        if not runtimes or not runtimes[0].is_runtime_ready():
            return
        if server:
            pcs = [p for p in u.GameplayStatics.get_all_actors_of_class(world, u.PlayerController) if p.get_controlled_pawn()]
            if len(pcs) < 2 and 'target' not in state:
                return
            if 'target' not in state:
                animals = [inspect(world, k) for k in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)]
                animal = next(a for a in animals if a.get('species') == 'Wolf' and a.get('hp', 0) > 0)
                state.update(target=int(animal['stable_id']), start=None)
            animal = inspect(world, state['target'])
            now = time.time()
            elapsed = now-state['start'] if state['start'] else 0.
            focus = animal
            if elapsed >= 29.5:
                if 'deer' not in state:
                    animals = (inspect(world, k) for k in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world))
                    deer = next((a for a in animals if a.get('species') == 'Herbivore' and a.get('hp', 0) > 0), None)
                    assert deer, 'The second species must exist on authority'
                    state['deer'] = int(deer['stable_id'])
                focus = inspect(world, state['deer'])
            if focus.get('native_world_position') and focus.get('hp', 0) > 0:
                point = u.Vector(*focus['native_world_position'])
                for index, pc in enumerate(pcs):
                    pawn = pc.get_controlled_pawn()
                    pawn.player_state.set_invulnerable(True)
                    pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
                    # Keep both clients inside visual relevance. The observer stays off the firing line.
                    active_client = 'A' if elapsed < 12 else 'B'
                    try:
                        marker = json.loads((out/(active_client+'_Pawn.json')).read_text())
                        active = marker.get('run_id') == run_id and marker.get('player_id') == pawn.player_state.get_editor_property('player_id')
                    except (OSError, ValueError):
                        active = index == 0
                    offset = u.Vector(-420 if active else -380, 0 if active else 270, 96)
                    pawn.set_actor_location(point+offset, False, True)
                    pawn.character_movement.stop_movement_immediately()
                    pawn.set_actor_rotation(u.Rotator(0, 0, 0), True)
            if now > state.get('next_packet', 0.):
                state['next_packet'] = now+.03
                # Deterministic UI fixture aim: render interpolation must not turn this
                # into a moving-target marksmanship test. No animal/world values change.
                packet = dict(run_id=run_id, target=state['target'], start=state['start'], position=focus.get('native_world_position'))
                (out/'Session.json').write_text(json.dumps(packet))
            if not state['start']:
                try:
                    peers_ready = all(json.loads((out/(client+'_Ready.json')).read_text()).get('run_id') == run_id
                                      for client in ('A', 'B'))
                except (OSError, ValueError):
                    peers_ready = False
                if peers_ready:
                    state['start'] = now
                return
            if elapsed > state['next_sample']:
                state['next_sample'] = elapsed+.03
                state['samples'].append(dict(elapsed=elapsed, hp=animal.get('hp', 0)))
            if elapsed > 35:
                for client in ('A', 'B'):
                    if not (out/(client+'.json')).exists():
                        assert elapsed < 42, 'Missing peer report '+client
                        return
                    report = json.loads((out/(client+'.json')).read_text())
                    if report.get('run_id') != run_id:
                        assert elapsed < 42, 'Missing fresh peer report '+client
                        return
                    assert report['result'] == 'PASS', client+' failed: '+report['error']
                    assert report['input_shots'] > 0, client+' must request an attack'
                for start, end in ((3, 11), (12, 29)):
                    values = [s['hp'] for s in state['samples'] if start <= s['elapsed'] <= end]
                    assert values and max(values)-min(values) > 0, 'Authority HP did not decrease in attack phase '+str(start)
                finish(True)
            return
        if not (out/'Session.json').exists():
            return
        try:
            session = json.loads((out/'Session.json').read_text())
        except (OSError, ValueError):
            return
        if session.get('run_id') != run_id:
            return
        elapsed = time.time()-session['start'] if session['start'] else 0.
        pc = u.GameplayStatics.get_player_controller(world, 0)
        pawn = pc.get_controlled_pawn()
        if not pawn or not pawn.player_state:
            return
        if not state.get('bound'):
            pawn.get_component_by_class(u.EcoWeaponFireComponent).on_damage_outcome.add_callable(outcome)
            (out/(name+'_Pawn.json')).write_text(json.dumps(dict(run_id=run_id, player_id=pawn.player_state.get_editor_property('player_id'))))
            state['bound'] = True
        visuals = [v for v in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor) if v.get_editor_property('bound')]
        target = next((v for v in visuals if int(v.visual_state.stable_agent_id) == session['target']), None)
        if session.get('position'):
            camera = pawn.get_component_by_class(u.CameraComponent)
            point = u.Vector(*session['position'])
            pc.set_control_rotation(u.MathLibrary.find_look_at_rotation(camera.get_world_location(), point+u.Vector(0, 0, 45)))
        if target:
            # The adapter defers scripted input beyond the editor RPC-local scope.
            avatar = pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
            equipment = pawn.get_component_by_class(u.EcoEquipmentComponent)
            if equipment.get_editor_property('weapon') and not state.get('aim_pressed'):
                state['aim_pressed'] = True
                avatar.press_configured_action(aim)
            if state.get('aim_pressed') and not state.get('ready_sent'):
                state['ready_sent'] = True
                (out/(name+'_Ready.json')).write_text(json.dumps(dict(run_id=run_id)))
            window = (4, 10) if name == 'A' else (13, 27)
            if window[0] < elapsed < window[1]:
                state.setdefault('attack_baseline', target.visual_state.normalized_health)
            if window[0] < elapsed < window[1] and elapsed > state['next_shot'] and target.visual_state.normalized_health >= state['attack_baseline']-.01:
                state['next_shot'] = elapsed+.8
                state['shots'] += 1
                avatar.release_configured_action(fire)
                avatar.press_configured_action(fire)
        # Every received species uses the same component, without a local health writer.
        if elapsed > state['next_sample']:
            state['next_sample'] = elapsed+.1
            bars = []
            for visual in visuals:
                sample = visual.visual_state
                bar = visual.get_component_by_class(u.EcoHealthBarComponent)
                assert bar, 'Missing inherited health bar'
                assert bar.has_health_sample() == sample.has_vitals, 'Unknown vitals fabricated'
                if sample.has_vitals:
                    expected = sample.normalized_health if sample.alive else 0
                    assert bar.is_visible(), 'Known health bar hidden'
                    assert abs(bar.get_health_fraction()-expected) < .00001, 'Display differs from received HP'
                    if '-HealthBarRender' in cmd:
                        assert bar.get_user_widget_object(), 'Rendered health widget was not initialized'
                bars.append(dict(id=int(sample.stable_agent_id), species=str(sample.species_id), fraction=bar.get_health_fraction()))
            state['samples'].append(dict(elapsed=elapsed, bars=bars))
        if '-HealthBarRender' in cmd and name == 'A' and elapsed > 30 and not state.get('screenshot'):
            state['screenshot'] = True
            u.SystemLibrary.execute_console_command(world, 'Shot SHOWUI')
        if elapsed > 33:
            assert not u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world), 'Client executed authority'
            assert state['shots'] > 0, 'Configured attack required from each client'
            fractions = [(s['elapsed'], b['fraction']) for s in state['samples'] for b in s['bars'] if b['id'] == session['target']]
            for start, end in ((3, 11), (12, 29)):
                values = [hp for t, hp in fractions if start <= t <= end]
                assert values and max(values)-min(values) > .01, 'Missing shared HP reduction during attack phase '+str(start)
            assert {'Wolf', 'Herbivore'}.issubset({b['species'] for s in state['samples'] for b in s['bars']}), 'Both species must display health'
            finish(True)
    except Exception:
        finish(False, traceback.format_exc())

def ticker(dt):
    # Synchronous Unreal work can pump tickers; never issue a nested input/RPC.
    if state.get('in_tick') or state.get('done'):
        return not state.get('done', False)
    state['in_tick'] = True
    try:
        tick(dt)
    finally:
        state['in_tick'] = False
    return not state.get('done', False)

handle = u.register_ticker_callback(ticker, 0.0)

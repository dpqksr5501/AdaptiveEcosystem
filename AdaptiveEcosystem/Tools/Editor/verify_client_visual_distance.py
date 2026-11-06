"""Development QA: only move the server player and edit the client's visual distance.

Never move creatures or write logical state. Observe proxy survival, pooled visual
re-entry, and authority map positions while the client's representation is absent.
"""
import json
import time
import traceback
from pathlib import Path
import unreal as u

server = '-VisualDistanceServer' in u.SystemLibrary.get_command_line()
out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / 'ClientVisualDistanceValidation'
out.mkdir(parents=True, exist_ok=True)
state = dict(deadline=time.monotonic()+150, samples=[], next_sample=0, phase=-1)


def capture(world, key):
    value = u.EcoCreatureInspectionLibrary.capture_agent(world, key)
    if isinstance(value, tuple):
        value = next(v for v in value if isinstance(v, str))
    return json.loads(value) if value else {}


def finish(ok, error=''):
    state['done'] = True
    name = 'Server' if server else 'Client'
    (out/(name+'.json')).write_text(json.dumps(dict(result='PASS' if ok else 'FAIL', error=error,
        samples=state['samples']), indent=2), encoding='utf-8')
    u.log('[ClientVisualDistance] '+name+' '+('PASS' if ok else 'FAIL '+error))
    if state.get('world'):
        u.SystemLibrary.execute_console_command(state['world'], 'QUIT')


def tick(dt):
    try:
        assert time.monotonic() < state['deadline'], 'Fixture timeout'
        world = next((w for w in u.ObjectIterator(u.World) if w.get_name() == 'LV_JYU_HerdMigration'
            and u.GameplayStatics.get_game_state(w) and (server or u.GameplayStatics.get_player_controller(w, 0))), None)
        state['world'] = world
        if not world:
            return
        runtimes = u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureIntegrationSpawner)
        if not runtimes or not runtimes[0].is_runtime_ready():
            return
        runtime = runtimes[0]
        if server:
            # The client may disconnect before the next server tick; finalize independently of its pawn.
            if (out/'Client.json').exists():
                report = json.loads((out/'Client.json').read_text())
                assert report['result'] == 'PASS', report['error']
                assert len(state['samples']) > 10, 'Insufficient authority observations'
                assert state['samples'][0]['position'] != state['samples'][-1]['position'], 'Authority target did not continue moving'
                finish(True)
                return
            pcs = [pc for pc in u.GameplayStatics.get_all_actors_of_class(world, u.PlayerController) if pc.get_controlled_pawn()]
            if not pcs:
                return
            if 'target' not in state:
                animals = [capture(world, key) for key in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)]
                animal = next(a for a in animals if a.get('species') == 'Herbivore' and a.get('hp', 0) > 0)
                state.update(target=int(animal['stable_id']), start=time.time())
                (out/'Session.json').write_text(json.dumps(dict(target=state['target'], start=state['start'])))
            animal = capture(world, state['target'])
            assert animal.get('hp', 0) > 0, 'Target lost on authority'
            point = u.Vector(*animal['native_world_position'])
            for pc in pcs:
                pawn = pc.get_controlled_pawn()
                pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
                pawn.set_actor_location(point+u.Vector(-300, 0, 96), False, True)
                pawn.character_movement.stop_movement_immediately()
            elapsed = time.time()-state['start']
            if elapsed >= state['next_sample']:
                state['next_sample'] = elapsed+.25
                raw = u.EcoCreatureInspectionLibrary.capture_migration(world)
                if isinstance(raw, tuple):
                    raw = next(v for v in raw if isinstance(v, str))
                overview = json.loads(raw)
                members = overview['members']
                assert any(int(row['agent']) == state['target'] for row in members), 'Logical target missing from authority map'
                state['samples'].append(dict(elapsed=elapsed, map_members=len(members), position=animal['native_world_position']))
            return
        if not (out/'Session.json').exists():
            return
        session = json.loads((out/'Session.json').read_text())
        elapsed = time.time()-session['start']
        # Exercise the authored short default, then disappear/reappear twice and disable the limit.
        distances = (1000., 1., 1000., 1., 0.)
        phase = min(int(elapsed/5), len(distances)-1)
        if phase != state['phase']:
            state['phase'] = phase
            if phase == 0:
                assert runtime.get_editor_property('client_visual_distance') == 1000., 'Short editor default not loaded'
            runtime.set_editor_property('client_visual_distance', distances[phase])
        pc = u.GameplayStatics.get_player_controller(world, 0)
        proxy = capture(world, session['target'])
        visuals = [v for v in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor)
            if v.get_editor_property('bound')]
        target = next((v for v in visuals if int(v.visual_state.stable_agent_id) == session['target']), None)
        if target:
            pc.set_control_rotation(u.MathLibrary.find_look_at_rotation(pc.player_camera_manager.get_camera_location(), target.get_actor_location()))
        if elapsed >= state['next_sample'] and elapsed-phase*5 > 2:
            state['next_sample'] = elapsed+.25
            assert not u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world), 'Client contains logical authority'
            assert proxy and not proxy['authority'], 'Receive proxy lost when only visuals should be culled'
            camera = pc.player_camera_manager.get_camera_location()
            distances_cm = [(v.get_actor_location()-camera).length() for v in visuals]
            if distances[phase] > 0:
                assert all(d <= distances[phase]+100 for d in distances_cm), 'Visual exceeds configured range'
            if phase in (1, 3):
                assert not visuals and runtime.get_visual_count() == 0, 'Distant visual remained bound'
            else:
                assert target, 'Target did not re-enter local representation'
            state['samples'].append(dict(elapsed=elapsed, phase=phase, limit=distances[phase], actors=len(visuals),
                target_visible=bool(target), proxy_present=bool(proxy), distances_cm=distances_cm))
        if elapsed > 24:
            assert set(s['phase'] for s in state['samples']) == set(range(5)), 'Missing distance phase'
            finish(True)
    except Exception:
        finish(False, traceback.format_exc())


def ticker(dt):
    tick(dt)
    return not state.get('done', False)


handle = u.register_ticker_callback(ticker, 0.0)

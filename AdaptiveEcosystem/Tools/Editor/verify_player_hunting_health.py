"""Existing-level PIE fixture: actual wolf execution -> GAS HP -> death -> new Pawn.
Only the authority player's placement is controlled. Never edits HP, wolves or food.
"""
import json,time,traceback
from pathlib import Path
import unreal as u
MAP='/Game/JWJ/1102_Integration_JWJ'
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert levels.load_level(MAP)
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'PlayerHunting_20261105'
state=dict(start=None,deadline=time.monotonic()+120,pawn=None,dead=False,samples=[],target=None,next=0)
levels.editor_request_begin_play()
def finish(ok,error=None):
    (out/'PIE_PlayerHealth.json').write_text(json.dumps(dict(result='PASS' if ok else 'FAIL',error=error,samples=state['samples'],fixture='Actual wolf damage and player placement only'),indent=2),encoding='utf-8')
    u.log('PLAYER_HEALTH_PIE_'+('PASS' if ok else 'FAIL'))
    u.unregister_slate_post_tick_callback(handle);levels.editor_request_end_play();u.SystemLibrary.quit_editor()
def tick(dt):
    try:
        if time.monotonic()>state['deadline']:raise AssertionError('Wolf damage/death/respawn timeout')
        world=editor.get_game_world()
        if not world:return
        runtimes=u.GameplayStatics.get_all_actors_of_class(world,u.EcoCreatureIntegrationSpawner)
        if not runtimes or not runtimes[0].is_runtime_ready():return
        runtime=runtimes[0];pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn:return
        ps=pawn.get_editor_property('player_state')
        now=u.GameplayStatics.get_time_seconds(world)
        if state['pawn'] is None:state['pawn']=pawn.get_path_name();state['start']=now
        if pawn.get_path_name()!=state['pawn']:
            assert state['dead'] and ps.get_health()==100,'New healthy avatar required after death'
            assert runtime.get_combat_diagnostics().player_hits>=5,'Five actual wolf damage commits required'
            finish(True);return
        if not ps.is_alive():state['dead']=True
        if not state['dead']:
            wolves=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.EcoCreatureRepresentationActor)
                    if a.get_editor_property('bound') and str(a.get_editor_property('visual_species_id'))=='Wolf'
                    and a.get_editor_property('visual_state').alive]
            if wolves:
                wolf=wolves[0]
                forward=wolf.get_actor_forward_vector()
                point=wolf.get_actor_location()+forward*140+u.Vector(0,0,96)
                pawn.set_actor_location(point,False,True);pawn.character_movement.stop_movement_immediately()
        if now>=state['next']:
            state['next']=now+.2
            stats=runtime.get_combat_diagnostics()
            state['samples'].append(dict(time=now,hp=ps.get_health(),dead=state['dead'],attacks=stats.wolf_attacks,hits=stats.player_hits,pawn=pawn.get_path_name()))
        if now-state['start']>45:raise AssertionError('No completed wolf damage and respawn within 45 game seconds')
    except Exception:finish(False,traceback.format_exc())
handle=u.register_slate_post_tick_callback(tick)

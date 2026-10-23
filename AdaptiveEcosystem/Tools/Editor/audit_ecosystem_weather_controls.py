"""Actual PIE acceptance of received-weather controls; no climate/food/agent writes."""
import json,time
from pathlib import Path
import unreal

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if 'LV_JYU_Ecosystem' not in editor.get_editor_world().get_name():raise RuntimeError('Owned ecosystem map required')
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(editor.get_editor_world()):raise RuntimeError('Partition not ready')
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'EcosystemBP_20261023'
state=dict(start=None,camera=None,next=0,phase=None,rows=[],error=None)
deadline=time.monotonic()+100
levels.editor_request_begin_play()

def finish():
    unreal.unregister_slate_post_tick_callback(handle)
    rows=state['rows']
    off=[r for r in rows if 3<r['elapsed']<5]
    on=[r for r in rows if 9<r['elapsed']<12]
    end=[r for r in rows if r['elapsed']>15]
    passed=bool(not state['error'] and off and on and end
        and all(r['rain']>.6 and not r['rain_on'] and not r['sound_on'] for r in off+end)
        and all(r['rain_on'] and r['sound_on'] and r['rate_valid'] and abs(r['rate']-1000*r['rain'])<1 for r in on)
        and end[-1]['step']>off[0]['step'] and end[-1]['moisture']>off[0]['moisture'])
    report=dict(passed=passed,error=state['error'],samples=rows,
        scenario='Saved BP climate; visuals 0->1(density2)->0. No weather/food/agent overrides')
    (out/'WeatherControls.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('ECOSYSTEM_WEATHER_CONTROLS_FINISHED '+str(passed))
    levels.editor_request_end_play();unreal.SystemLibrary.quit_editor()

def tick(dt):
    try:
        if time.monotonic()>deadline:raise RuntimeError('Weather controls deadline')
        game=editor.get_game_world()
        if not game:return
        spawners=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureIntegrationSpawner)
        if not spawners or not spawners[0].is_runtime_ready():return
        fields=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoVegetationField)
        field=next((f for f in fields if str(f.get_editor_property('region_id'))=='Highland'),None)
        if not field:return
        if state['camera'] is None:
            group=next(g for g in spawners[0].get_editor_property('groups') if str(g.get_editor_property('region_id'))=='Highland')
            pos=group.get_editor_property('food_patch_position')+unreal.Vector(0,0,250)
            state['camera']=unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(game,unreal.CameraActor,unreal.Transform(location=pos))
            unreal.GameplayStatics.get_player_controller(game,0).set_view_target_with_blend(state['camera'],0)
        grid=json.loads(field.capture_diagnostics())
        # The saved map starts dry. Wait for its real climate cycle instead of
        # assuming rain at time zero or forcing an authoritative weather fixture.
        if state['start'] is None:
            if grid['rain']<=.6:return
            state['start']=time.monotonic()
        elapsed=time.monotonic()-state['start']
        if elapsed>=18:finish();return
        if elapsed<state['next']:return
        state['next']=elapsed+.25
        for pawn in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.Pawn):
            for cls in (unreal.EcoPlayerEcologyComponent,unreal.EcoThreatSourceComponent):
                for component in pawn.get_components_by_class(cls):component.set_editor_property('threat_enabled',False)
        phase=0 if elapsed<5 or elapsed>=12 else 1
        if phase!=state['phase']:
            unreal.SystemLibrary.execute_console_command(game,'eco.IntegratedV3.WeatherRainDensity 2')
            unreal.SystemLibrary.execute_console_command(game,'eco.IntegratedV3.WeatherVisuals '+str(phase))
            state['phase']=phase
        fx=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoV3WeatherFxActor)
        f=fx[0] if fx else None
        # Inspect the actual public component APIs. Transient C++ diagnostic
        # members are protected from Python and are not needed for acceptance.
        rain=next((c for c in f.get_components_by_class(unreal.NiagaraComponent) if c.get_name().startswith('RainSystem')),None) if f else None
        audio=f.get_components_by_class(unreal.AudioComponent) if f else []
        rate=rain.get_variable_float('SpawnRate') if rain else (0,False)
        if isinstance(rate,tuple):
            rate_valid=next((v for v in rate if isinstance(v,bool)),False)
            rate_value=next((v for v in rate if isinstance(v,(float,int)) and not isinstance(v,bool)),0)
        else:raise RuntimeError('Unexpected Niagara getter result '+repr(rate))
        state['rows'].append(dict(elapsed=elapsed,enabled=phase,rain=grid['rain'],moisture=grid['mean_moisture'],step=grid['native_step'],
            rain_on=rain.is_active() if rain else False,sound_on=any(c.is_playing() for c in audio),
            rate=rate_value,rate_valid=rate_valid))
    except Exception as e:
        state['error']=repr(e);unreal.log_error('ECOSYSTEM_WEATHER_CONTROLS_ERROR '+repr(e));finish()
handle=unreal.register_slate_post_tick_callback(tick)

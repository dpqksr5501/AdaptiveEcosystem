"""Real owned-map observation: explicit rain fixture only, no food/agent/policy writes.
Use -VegetationPIE for Editor PIE; otherwise binds to server completion relay.
Outputs source verification data to Saved, never personal presentation files.
"""
import json, math, re, time
from pathlib import Path
import unreal

cmd = unreal.SystemLibrary.get_command_line()
def arg(key, default):
    m = re.search(r'-' + key + r'=([^\s"]+)', cmd, re.I)
    return m.group(1) if m else default
name = arg('VegetationAuditName', 'PIE')
duration = float(arg('VegetationAuditDuration', '125'))
if not math.isfinite(duration) or not 1<=duration<=3600:raise RuntimeError('Finite bounded observation duration required')
if not re.fullmatch(r'[A-Za-z0-9_]+',name):raise RuntimeError('Simple report name required')
pie = '-vegetationpie' in cmd.lower()
authored = '-vegetationauthored' in cmd.lower()
map_name = arg('VegetationMap','LV_JYU_HerdMigration')
folder = arg('VegetationAuditFolder','Vegetation_20261023')
if map_name not in ('LV_JYU_HerdMigration','LV_JYU_Ecosystem') or not re.fullmatch(r'[A-Za-z0-9_]+',folder):raise RuntimeError('Owned map/output folder required')
out = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / folder
out.mkdir(parents=True, exist_ok=True)
state = dict(start=None, next=0, rows=[], error=None, phase=None, camera=None, shots=0, focus=None, hidden=False, last={}, transfers=[],world=None,csv=False,child_visuals=[])
deadline = time.monotonic() + duration + 180
if pie:
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if map_name not in editor.get_editor_world().get_name():
        if not levels.load_level('/Game/JYU/Maps/'+map_name):
            unreal.SystemLibrary.quit_editor();raise RuntimeError('Owned map could not be opened; no maps saved')
    if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(editor.get_editor_world()):
        raise RuntimeError('World partition preparation failed')
    levels.editor_request_begin_play()
def world():
    if pie: return editor.get_game_world()
    if state['world'] is None:
        state['world']=next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name()==map_name
            and unreal.GameplayStatics.get_game_state(w) is not None),None)
    return state['world']
def finish(result):
    if result=='FINISHED' and pie and '-vegetationlifefocus' in cmd.lower() and not state['child_visuals']:
        result='FAILED';state['error']='No actual natural child representation/animation was observed'
    if state['csv']:unreal.SystemLibrary.execute_console_command(world(),'csvprofile STOP')
    if pie: unreal.unregister_slate_post_tick_callback(handle)
    else: relay.on_runtime_sample.remove_callable(tick)
    report = dict(result=result, error=state['error'], fixture=('Authored BP climate; no weather/food/agent writes; observer threats disabled' if authored else 'World rainfall=0 then 0.65; no direct food removal/refill; observer threats disabled'),
                  duration_wall_seconds=duration, samples=state['rows'], screenshots=state['shots'], region_transfers=state['transfers'],child_visuals=state['child_visuals'],overlap_expected='-vegetationoverlapexpected' in cmd.lower())
    (out / (name + '_Runtime.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('VEGETATION_AUDIT_FINISHED ' + json.dumps(dict(result=result, error=state['error'], samples=len(state['rows']))))
    if pie:
        levels.editor_request_end_play()
        unreal.SystemLibrary.quit_editor()
def tick(dt):
    try:
        if time.monotonic() > deadline: raise RuntimeError('Initialization/observation deadline')
        game = world()
        if not game: return
        spawners = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcoCreatureIntegrationSpawner)
        if not spawners or not spawners[0].is_runtime_ready(): return
        fields = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcoVegetationField)
        if len(fields) != 3: return
        now = time.monotonic()
        if state['start'] is None: state['start'] = now
        elapsed = now - state['start']
        if not pie and not state['csv'] and elapsed>5:
            unreal.SystemLibrary.execute_console_command(game,'csvprofile STARTFILE=EcosystemLife_'+folder+'_'+name+'.csv')
            unreal.SystemLibrary.execute_console_command(game,'csvprofile START');state['csv']=True
        if pie and not state['hidden']:
            for command in ('eco.Creature.Labels 0', 'eco.Inspector.Visible 0', 'eco.HerdMigration.Debug 0'):
                unreal.SystemLibrary.execute_console_command(game, command)
            state['hidden'] = True
        if elapsed >= duration: finish('FINISHED'); return
        if elapsed < state['next']: return
        state['next'] = elapsed + 2
        for pawn in unreal.GameplayStatics.get_all_actors_of_class(game, unreal.Pawn):
            for cls in (unreal.EcoPlayerEcologyComponent, unreal.EcoThreatSourceComponent):
                for c in pawn.get_components_by_class(cls): c.set_editor_property('threat_enabled', False)
        phase = 'AuthoredCycle' if authored else ('Dry' if elapsed < duration / 2 else 'Rain')
        if not authored and phase != state['phase']:
            rain = 0.0 if phase == 'Dry' else 0.65
            weather = unreal.EcoWeatherState.DROUGHT if phase == 'Dry' else unreal.EcoWeatherState.RAIN
            regions = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcologyRegion)
            if len(regions) != 3: raise RuntimeError('Expected three authoritative World regions')
            for region in regions:
                environment = region.get_environment_state()
                environment.set_editor_property('rainfall', rain)
                environment.set_editor_property('weather_state', weather)
                region.set_environment_state(environment)
            state['phase'] = phase
        rows = []
        for field in fields:
            row=json.loads(field.capture_diagnostics());p=field.get_actor_location()
            row['actor_location']=[p.x,p.y,p.z]
            row['net_cull_distance_squared']=field.get_editor_property('net_cull_distance_squared')
            rows.append(row)
        keys = unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(game)
        agents = []
        for key in keys:
            raw = unreal.EcoCreatureInspectionLibrary.capture_agent(game, key)
            if isinstance(raw, tuple): raw = next((s for s in raw if isinstance(s, str)), None)
            if raw:
                agent = json.loads(raw)
                previous = state['last'].get(str(key))
                if previous and previous['region'] != agent['region']:
                    state['transfers'].append(dict(id=str(key), origin=previous['region'], destination=agent['region'], elapsed=elapsed,
                                                   previous=previous.get('native_world_position'), current=agent.get('native_world_position')))
                state['last'][str(key)] = agent
                agents.append(agent)
        pawn=unreal.GameplayStatics.get_player_pawn(game,0)
        camera=unreal.GameplayStatics.get_player_camera_manager(game,0)
        p=pawn.get_actor_location() if pawn else None;c=camera.get_camera_location() if camera else None
        native=next((n for n in unreal.ObjectIterator(unreal.EcoPolicyV3IntegratedSubsystem) if n.get_outer()==game),None)
        performance=json.loads(native.capture_step_performance()) if native else None
        state['rows'].append(dict(elapsed=elapsed, world_seconds=unreal.GameplayStatics.get_time_seconds(game), phase=phase, fields=rows, authority_agents=len(keys), agents=agents,performance=performance,players=len(unreal.GameplayStatics.get_all_actors_of_class(game,unreal.PlayerController)),
            observer_pawn=[p.x,p.y,p.z] if p else None,observer_camera=[c.x,c.y,c.z] if c else None))
        (out / (name + '_Progress.json')).write_text(json.dumps(state['rows'][-1], indent=2), encoding='utf-8')
        if pie:
            selected = next((f for f in fields if str(f.get_editor_property('region_id')) == 'Forest'), fields[0])
            plants = selected.get_editor_property('plants')
            count = plants.get_instance_count()
            if count:
                transform = plants.get_instance_transform(count//2, True)
                if isinstance(transform, tuple): transform = next(v for v in transform if isinstance(v, unreal.Transform))
                # Focus on an actual rendered cell; resource DTO internals stay private.
                if state['focus'] is None and elapsed > 5: state['focus'] = transform.translation + unreal.Vector(0,0,40)
                focus = state['focus'] or (transform.translation + unreal.Vector(0,0,40))
                if '-vegetationlifefocus' in cmd.lower():
                    if elapsed<40:
                        sources=[a for a in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoVegetationHabitat) if a.get_editor_property('connected_fresh_water')]
                        if sources:focus=sources[0].get_actor_location()+unreal.Vector(0,0,30)
                    else:
                        children=[a for a in agents if a.get('life',{}).get('origin')==1 and a.get('hp',0)>0 and a.get('native_world_position')]
                        if children:
                            child=next((a for a in children if a['species']=='Herbivore'),children[0])
                            focus=unreal.Vector(*child['native_world_position'])+unreal.Vector(0,0,45)
                            # The existing IK LOD uses the observer pawn's focal point.
                            # Move only the threat-disabled observer, never the animal.
                            observer=unreal.GameplayStatics.get_player_pawn(game,0)
                            ground=unreal.EcoCreatureAnimationBuilder.project_placement_point(game,focus+unreal.Vector(-1800,0,0))
                            if isinstance(ground,tuple):ground=next((v for v in ground if isinstance(v,unreal.Vector)),None)
                            if observer and isinstance(ground,unreal.Vector):observer.set_actor_location(ground+unreal.Vector(0,0,100),False,True)
                            for actor in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureRepresentationActor):
                                visual=actor.get_editor_property('visual_state')
                                if not actor.get_editor_property('bound') or str(visual.get_editor_property('stable_agent_id'))!=child['stable_id']:continue
                                mesh=actor.get_editor_property('creature_mesh');anim=mesh.get_anim_instance()
                                if anim is None:raise RuntimeError('Natural child representation has no actual animation instance')
                                scale=actor.get_actor_scale3d();payload=visual.get_editor_property('body_scale')
                                if abs(scale.x-payload)>1e-5:raise AssertionError('Natural child scale payload/actor mismatch')
                                state['child_visuals'].append(dict(elapsed=elapsed,id=child['stable_id'],species=child['species'],actor_scale=scale.x,
                                    native_scale=child['body_scale'],growth=child['life']['growth'],animation=anim.get_class().get_name(),
                                    animation_index=anim.get_editor_property('animation_index'),ik_alpha=anim.get_editor_property('ground_ik_alpha')))
                if state['camera'] is None:
                    state['camera'] = unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(game, unreal.CameraActor, unreal.Transform(location=focus))
                    unreal.GameplayStatics.get_player_controller(game,0).set_view_target_with_blend(state['camera'],0)
                pos = focus + unreal.Vector(-450,-650,450)
                state['camera'].set_actor_location(pos,False,False)
                state['camera'].set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(pos,focus),False)
            if count and state['shots'] < 3 and elapsed > 20 + state['shots'] * 40:
                path = str(out / ('VegetationPIE_' + str(state['shots']) + '.png')).replace('\\','/')
                unreal.SystemLibrary.execute_console_command(game, 'HighResShot 1280x720 filename="' + path + '"')
                state['shots'] += 1
    except Exception as error:
        state['error'] = repr(error); unreal.log_error('VEGETATION_AUDIT_ERROR ' + repr(error)); finish('FAILED')
if pie: handle = unreal.register_slate_post_tick_callback(tick)
else:
    game = world()
    relay = next(iter(unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcoCreatureIntegrationSpawner)), None) if game else None
    if not relay: raise RuntimeError('Dedicated runtime completion relay missing')
    relay.on_runtime_sample.add_callable(tick)
unreal.log('VEGETATION_AUDIT_BOUND')

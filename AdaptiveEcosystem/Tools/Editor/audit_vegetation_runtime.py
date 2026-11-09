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
depletion_check = '-vegetationgrassdepletioncheck' in cmd.lower()
grass_debug = '-vegetationgrassdebug' in cmd.lower() or depletion_check
dry_temperature = float(arg('VegetationGrassDryTemperature', '50' if depletion_check else '30'))
if not math.isfinite(dry_temperature) or not -100 <= dry_temperature <= 100:
    raise RuntimeError('Finite dry temperature within the existing climate contract required')
visual_check = '-vegetationgrassvisualcheck' in cmd.lower()
water_check = '-vegetationgrasswatercheck' in cmd.lower()
soil_off = '-vegetationgrasssoiloff' in cmd.lower()
feeding_check = '-vegetationgrassfeedingcheck' in cmd.lower()
grass_profile = '-vegetationgrassprofile' in cmd.lower()
patch_layout = '-vegetationpatchlayout' in cmd.lower().split()
network_profile = '-vegetationnetworkprofile' in cmd.lower().split()
if depletion_check and (not pie or duration < 90 or grass_profile or feeding_check or water_check or visual_check):
    raise RuntimeError('Depletion check requires PIE, at least 90 seconds, and no profile/feeding/water/visual-toggle mode')
if grass_profile and (feeding_check or '-vegetationlifefocus' in cmd.lower()):
    raise RuntimeError('Grass profiling excludes detailed feeding/life inspection')
if feeding_check and (not pie or duration < 30):
    raise RuntimeError('Grass feeding correlation requires PIE and at least 30 seconds')
if soil_off and (not pie or grass_debug or water_check or '-ecovegetation' in cmd.lower().split()):
    raise RuntimeError('Soil OFF check requires PIE with grass debug/water/EcoVegetation switches disabled')
grass_region = arg('VegetationGrassRegion', '')
if grass_debug and (duration < 30 or (grass_region and not re.fullmatch(r'[A-Za-z0-9_]+', grass_region))):
    raise RuntimeError('Grass debug observation requires at least 30 seconds and a simple region ID')
map_name = arg('VegetationMap', 'LV_JYU_Ecosystem' if feeding_check or grass_profile or depletion_check else 'LV_JYU_HerdMigration')
folder = arg('VegetationAuditFolder','Vegetation_20261023')
map_paths = {
    'LV_JYU_HerdMigration': '/Game/JYU/Maps/LV_JYU_HerdMigration',
    'LV_JYU_Ecosystem': '/Game/JYU/Maps/LV_JYU_Ecosystem',
    '1102_Integration_JWJ': '/Game/JWJ/1102_Integration_JWJ',
}
if map_name not in map_paths or not re.fullmatch(r'[A-Za-z0-9_]+',folder):raise RuntimeError('Approved map/output folder required')
jwj = map_name == '1102_Integration_JWJ'
expected_field_count = 4 if jwj else 3
jwj_camera_check = '-vegetationjwjcameracheck' in cmd.lower().split()
if jwj_camera_check and not (jwj and pie and authored and duration >= 52):
    raise RuntimeError('1102 camera check requires authored PIE for at least 52 seconds')
out = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / folder
out.mkdir(parents=True, exist_ok=True)
state = dict(start=None, next=0, rows=[], error=None, phase=None, camera=None, shots=0, focus=None, hidden=False, last={}, transfers=[],world=None,csv=False,child_visuals=[],observer_targets=[])
state['feeding'] = dict(synchronous_samples=0, source_cells=0, intake_samples=0, rendered=[], changes=[], pending={})
state['depletion'] = dict(synchronous_samples=0, positive={}, depleted={}, recovered={}, verified={})
deadline = time.monotonic() + duration + 180
if pie:
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if editor.get_editor_world().get_path_name().split('.')[0] != map_paths[map_name]:
        if not levels.load_level(map_paths[map_name]):
            unreal.SystemLibrary.quit_editor();raise RuntimeError('Owned map could not be opened; no maps saved')
    if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(editor.get_editor_world()):
        raise RuntimeError('World partition preparation failed')
    if patch_layout:
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'eco.Grass.PatchLayout 1')
    if soil_off:
        sources = [actor for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                   if isinstance(actor, unreal.EcoCreatureIntegrationSpawner)]
        if not sources:
            raise RuntimeError('An existing integration spawner is required for soil OFF check')
        state['authored_settings'] = [
            (source, source.get_editor_property('enable_vegetation'), source.get_editor_property('enable_food_grass'))
            for source in sources
        ]
        for source in sources:
            source.set_editor_property('enable_vegetation', False)
            source.set_editor_property('enable_food_grass', True)
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'eco.Vegetation 0')
    levels.editor_request_begin_play()
def world():
    if pie: return editor.get_game_world()
    if state['world'] is None:
        state['world']=next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name()==map_name
            and unreal.GameplayStatics.get_game_state(w) is not None),None)
    return state['world']
def finish(result):
    if depletion_check:
        audit = {key:value for key,value in state['depletion'].items() if key != 'verified'}
        audit['dry_temperature'] = dry_temperature
        audit['fixture'] = 'Existing climate commands only: dry/hot, rain/20C, Auto; no direct food writes'
        audit['checks'] = dict(synchronous_source=audit['synchronous_samples']>0,
            actual_zero_and_return=bool(audit['recovered']),
            consumed_increased=state.get('depletion_consumed_last',0)>state.get('depletion_consumed_first',0))
        if result == 'FINISHED' and not all(audit['checks'].values()):
            result = 'FAILED'; state['error'] = 'No verified positive -> exact zero/ISM removal -> same-cell regrowth/ISM return'
        audit['result'] = result
        (out / (name + '_Depletion.json')).write_text(json.dumps(audit,indent=2),encoding='utf-8')
    if result == 'FINISHED' and feeding_check:
        audit = state['feeding']
        if not (audit['synchronous_samples'] and audit['intake_samples'] and audit['rendered'] and audit['changes']):
            result = 'FAILED'
            state['error'] = 'No synchronous Native intake/source/DTO and subsequent actual ISM correlation'
    if feeding_check:
        audit = dict(state['feeding'])
        audit['pending'] = list(audit['pending'].values())
        (out / (name + '_Feeding.json')).write_text(json.dumps(audit, indent=2), encoding='utf-8')
    if result == 'FINISHED' and soil_off:
        rows = [row for sample in state['rows'] for row in sample['fields']]
        if not (rows and all(not row['soil'] for row in rows)
                and any(row['instances'] > 0 for row in rows)
                and all(abs(row['food'] - row['ledger_amount']) < 1e-6 for row in rows)
                and all(row['grown'] == 0 and row['environment_lost'] == 0 for row in rows)
                and state['rows'][-1]['fields'][0]['native_step'] > state['rows'][0]['fields'][0]['native_step']):
            result = 'FAILED'
            state['error'] = 'Soil OFF grass display, native progression or ledger regression'
    if result == 'FINISHED' and water_check:
        region = state.get('water_region')
        off = [next(row for row in sample['fields'] if row['region'] == region)
               for sample in state['rows'] if 20 <= sample['elapsed'] < 30]
        on = [next(row for row in sample['fields'] if row['region'] == region)
              for sample in state['rows'] if sample['elapsed'] >= 48]
        if not (region and off and on and all(row['connected_water_cells'] == 0 for row in off)
                and any(row['connected_water_cells'] > 0 for row in on)):
            result = 'FAILED'
            state['error'] = 'Authored water supply disconnect/reconnect did not reach soil inputs'
    if result == 'FINISHED' and visual_check:
        hidden = [sample for sample in state['rows'] if 10 <= sample['elapsed'] < 14]
        restored = [sample for sample in state['rows'] if sample['elapsed'] >= 24]
        hidden_ok = bool(hidden) and all(sum(row['instances'] for row in sample['fields']) == 0 for sample in hidden)
        resumed = bool(restored) and any(sum(row['instances'] for row in sample['fields']) > 0 for sample in restored)
        stepped = bool(hidden) and any(
            after['fields'][0]['native_step'] > before['fields'][0]['native_step']
            for before, after in zip(hidden, hidden[1:])
        )
        if not (hidden_ok and resumed and stepped):
            result = 'FAILED'
            state['error'] = 'Grass display toggle or continued native simulation failed'
    if result == 'FINISHED' and grass_debug:
        phases = {phase: [] for phase in ('Dry', 'Rain', 'Auto')}
        for sample in state['rows']:
            row = next(row for row in sample['fields'] if row['region'] == state['grass_region'])
            phases[sample['phase']].append(row)
        def applied(rows, rain, temperature):
            return any(row.get('manual_climate') and abs(row['rain'] - rain) < .001
                       and abs(row['temperature'] - temperature) < .01 for row in rows)
        all_rows = [row for sample in state['rows'] for row in sample['fields']]
        checks = (
            applied(phases['Dry'], 0, dry_temperature) and applied(phases['Rain'], .5, 20)
            and any(not row.get('manual_climate') for row in phases['Auto'])
            and all(not row.get('manual_climate') for row in all_rows if row['region'] != state['grass_region'])
            and all(abs(row['food'] - row['ledger_amount']) < 1e-6 for row in all_rows)
            and (not pie or any(row['instances'] > 0 for row in all_rows))
        )
        if not checks:
            result = 'FAILED'
            state['error'] = 'Grass debug climate, isolation, ledger or rendering gate failed'
    if result=='FINISHED' and pie and '-vegetationlifefocus' in cmd.lower() and not state['child_visuals']:
        result='FAILED';state['error']='No actual natural child representation/animation was observed'
    if result == 'FINISHED' and jwj and authored and not soil_off:
        rows = [field for sample in state['rows'] for field in sample['fields']]
        regions = {row['region'] for row in rows}
        rendered = {row['region'] for row in rows if row['instances'] > 0}
        valid = (len(regions) == expected_field_count
                 and all(row['soil'] and 'BP_JYU_VegetationField' in row['visual_class']
                         and abs(row['food'] - row['ledger_amount']) <= 1e-5 for row in rows)
                 and (not pie or rendered == regions))
        if not valid:
            result = 'FAILED'
            state['error'] = '1102 expected four JYU Fields with soil and matching ledger; PIE must display each'
        if valid and jwj_camera_check:
            for region in regions:
                observations = {sample.get('camera_turn') for sample in state['rows']
                                if sample.get('camera_region') == region
                                and abs((sample['observer_camera_yaw'] - sample['camera_turn'] + 180) % 360 - 180) <= 15
                                and any(row['region'] == region and row['near_instances'] > 0
                                        for row in sample['fields'])}
                if observations != {0, 180}:
                    result = 'FAILED'
                    state['error'] = '1102 grass missing after arrival/rotation: ' + region
    if state['csv']:unreal.SystemLibrary.execute_console_command(world(),'csvprofile STOP')
    if network_profile:unreal.SystemLibrary.execute_console_command(world(),'netprofile disable')
    if pie: unreal.unregister_slate_post_tick_callback(handle)
    else: relay.on_runtime_sample.remove_callable(tick)
    fixture = ('Transient existing spawner: soil OFF, food grass ON; no asset save' if soil_off
               else 'Regional grass debug dry/rain/auto; no direct food writes' if grass_debug
               else 'Authored BP climate' if authored else 'World rainfall=0 then 0.65; no direct food removal/refill')
    if result == 'FINISHED' and patch_layout:
        latest = state['rows'][-1]['fields'] if state['rows'] else []
        if not (len(latest) == expected_field_count and all(
                f.get('patch_layout_mode') == 1 and f.get('patch_layout_count', 0) > 0
                and f.get('published_patch_anchors', 0) > 0 for f in latest)
                and all(f.get('patch_world_ground_traces_this_frame', 97) <= 96
                        for s in state['rows'] for f in s['fields'])):
            result = 'FAILED'; state['error'] = 'S1 layout readiness/authority world trace budget failed'
    report = dict(result=result, error=state['error'], fixture=fixture, patch_layout=patch_layout,
                  duration_wall_seconds=duration, grass_profile=grass_profile, samples=state['rows'], screenshots=state['shots'], region_transfers=state['transfers'],child_visuals=state['child_visuals'],observer_targets=state['observer_targets'],overlap_expected='-vegetationoverlapexpected' in cmd.lower())
    (out / (name + '_Runtime.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('VEGETATION_AUDIT_FINISHED ' + json.dumps(dict(result=result, error=state['error'], samples=len(state['rows']))))
    if pie:
        levels.editor_request_end_play()
        for source, vegetation, food_grass in state.get('authored_settings', []):
            source.set_editor_property('enable_vegetation', vegetation)
            source.set_editor_property('enable_food_grass', food_grass)
        if grass_profile and state['csv']:
            # CSV writes asynchronously. Keep editor frames running until its footer is complete.
            csv_path = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / 'Profiling/CSV' / ('EcosystemLife_' + folder + '_' + name + '.csv')
            flush_deadline = time.monotonic() + 30
            def wait_csv_flush(dt):
                complete = False
                if csv_path.is_file():
                    try:
                        with csv_path.open('rb') as stream:
                            stream.seek(max(0, csv_path.stat().st_size - 16384))
                            tail = stream.read()
                    except OSError:
                        # Windows CSV writer briefly owns the file exclusively while finalizing.
                        # This is a pending read, not a completed/failed capture; keep the same deadline.
                        tail = b''
                    # UE's final metadata line has no trailing newline. Wait for its size to settle.
                    size = csv_path.stat().st_size if csv_path.exists() else 0
                    if state.get('csv_final_size') != size:
                        state['csv_final_size'] = size
                        state['csv_stable_since'] = time.monotonic()
                    complete = b'[HasHeaderRowAtEnd],1,' in tail and time.monotonic() - state['csv_stable_since'] >= .1
                if not complete and time.monotonic() < flush_deadline: return
                if not complete:
                    report['result'] = 'FAILED'
                    report['error'] = 'CSV flush deadline; profile is incomplete'
                    (out / (name + '_Runtime.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                    unreal.log_error('VEGETATION_PROFILE_CSV_INCOMPLETE')
                else: unreal.log('VEGETATION_PROFILE_CSV_FLUSHED')
                unreal.unregister_slate_post_tick_callback(state['flush_handle'])
                unreal.SystemLibrary.quit_editor()
            state['flush_handle'] = unreal.register_slate_post_tick_callback(wait_csv_flush)
        else: unreal.SystemLibrary.quit_editor()
def tick(dt):
    try:
        if time.monotonic() > deadline: raise RuntimeError('Initialization/observation deadline')
        game = world()
        if not game: return
        spawners = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcoCreatureIntegrationSpawner)
        if not spawners or not spawners[0].is_runtime_ready(): return
        fields = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcoVegetationField)
        if len(fields) != expected_field_count: return
        now = time.monotonic()
        if state['start'] is None: state['start'] = now
        elapsed = now - state['start']
        if (not pie or grass_profile) and not state['csv'] and elapsed>5:
            unreal.SystemLibrary.execute_console_command(game,'csvprofile STARTFILE=EcosystemLife_'+folder+'_'+name+'.csv')
            unreal.SystemLibrary.execute_console_command(game,'csvprofile START');state['csv']=True
        if pie and not state['hidden']:
            for command in ('eco.Creature.Labels 0', 'eco.Inspector.Visible 0', 'eco.HerdMigration.Debug 0'):
                unreal.SystemLibrary.execute_console_command(game, command)
            state['hidden'] = True
        if elapsed >= duration: finish('FINISHED'); return
        if jwj_camera_check and 24 <= elapsed < 48:
            index = int((elapsed - 24) // 3)
            if index != state.get('camera_phase'):
                regions = sorted(unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcologyRegion),
                                 key=lambda actor: str(actor.get_editor_property('region_id')))
                region = regions[index // 2]
                turn = (index % 2) * 180
                controller = unreal.GameplayStatics.get_player_controller(game, 0)
                pawn = unreal.GameplayStatics.get_player_pawn(game, 0)
                if not controller or not pawn:
                    raise RuntimeError('1102 camera fixture requires the existing player')
                if not turn:
                    location = region.get_actor_location() + unreal.Vector(0, 0, 150)
                    if not pawn.set_actor_location(location, False, True):
                        raise RuntimeError('1102 camera fixture player movement failed')
                controller.set_control_rotation(unreal.Rotator(pitch=-15, yaw=turn))
                state.update(camera_phase=index, camera_region=str(region.get_editor_property('region_id')),
                             camera_turn=turn, camera_changed=elapsed)
        if depletion_check and elapsed >= state.get('depletion_next',0):
            state['depletion_next'] = elapsed + .1
            region = state.get('grass_region', grass_region or str(sorted(fields,key=lambda f:str(f.get_editor_property('region_id')))[0].get_editor_property('region_id')))
            field = next(f for f in fields if str(f.get_editor_property('region_id'))==region)
            snapshot = json.loads(field.capture_diagnostics(True))
            audit = state['depletion']
            if not snapshot['soil']: raise AssertionError('Depletion check requires the existing soil-enabled world')
            state.setdefault('depletion_consumed_first',snapshot['consumed'])
            state['depletion_consumed_last'] = snapshot['consumed']
            if abs(snapshot['food']-snapshot['ledger_amount'])>1e-6: raise AssertionError('Depletion FoodGrid/M4 mismatch')
            if snapshot['native_step']==snapshot['published_native_step'] and snapshot['native_step']!=state.get('depletion_step'):
                state['depletion_step'] = snapshot['native_step'];audit['synchronous_samples'] += 1
                for cell in snapshot['visual_samples']:
                    if cell['food_code']!=cell['source_food_code'] or cell['capacity_code']!=cell['source_capacity_code']:
                        raise AssertionError('Depletion synchronous Native/DTO mismatch')
                audit['verified'] = {cell['cell']:dict(cell,source_step=snapshot['native_step']) for cell in snapshot['visual_samples']}
            camera = unreal.GameplayStatics.get_player_camera_manager(game,0)
            eye = camera.get_camera_location() if camera else None
            origin=snapshot['native_origin_cm'];width=snapshot['grid_width'];size=snapshot['cell_size_units']*snapshot['native_unit_cm']
            radius=max(field.get_editor_property('detail_radius_cm'),math.sqrt(field.get_editor_property('net_cull_distance_squared')))
            for cell in snapshot['visual_samples']:
                source=audit['verified'].get(cell['cell'])
                if not source or source['source_step']!=snapshot['published_native_step'] or source['food_code']!=cell['food_code'] or source['capacity_code']<=0: continue
                key=cell['cell'];x=origin[0]+(key%width+.5)*size;y=origin[1]+(key//width+.5)*size
                if not eye or (eye.x-x)**2+(eye.y-y)**2>radius**2: continue
                record=dict(elapsed=elapsed,phase=state['phase'],cell=key,source_step=source['source_step'],food=source['source_food'],
                    food_code=cell['food_code'],capacity_code=cell['capacity_code'],instances=cell['instances'],consumed=snapshot['consumed'])
                rendered=cell['instances']>0 and cell['matching_instances']==cell['instances']
                if state['phase']=='Dry' and source['source_food']>0 and rendered:
                    audit['positive'].setdefault(key,record)
                elif state['phase']=='Dry' and key in audit['positive'] and source['source_food']==0 and cell['food_code']==0 and cell['instances']==0:
                    audit['depleted'].setdefault(key,record)
                elif state['phase']=='Rain' and key in audit['depleted'] and source['source_food']>0 and rendered:
                    audit['recovered'].setdefault(key,record)
        if feeding_check and elapsed >= state.get('feeding_next', 0):
            state['feeding_next'] = elapsed + .1
            field = next((f for f in fields if str(f.get_editor_property('region_id')) == (grass_region or 'Forest')), None)
            if field is None: raise RuntimeError('Feeding audit region absent')
            snapshot = json.loads(field.capture_diagnostics(True))
            audit = state['feeding']
            cells = {cell['cell']: cell for cell in snapshot['visual_samples']}
            # Rendering can follow publication by one local refresh; never compare different source steps.
            for cell, pending in list(audit['pending'].items()):
                visual = cells.get(cell)
                if visual and visual['food_code'] == pending['food_code'] and visual['instances'] > 0 and visual['matching_instances'] == visual['instances']:
                    audit['rendered'].append(dict(pending, render_elapsed=elapsed, instances=visual['instances']))
                    del audit['pending'][cell]
            if snapshot['native_step'] == snapshot['published_native_step'] and snapshot['native_step'] != state.get('feeding_step'):
                state['feeding_step'] = snapshot['native_step']
                audit['synchronous_samples'] += 1
                if any(c['food_code'] != c['source_food_code'] or c['capacity_code'] != c['source_capacity_code'] for c in cells.values()):
                    raise AssertionError('Published grass DTO differs from synchronous Native source')
                if abs(snapshot['food'] - snapshot['ledger_amount']) > 1e-6:
                    raise AssertionError('FoodGrid/M4 mismatch during feeding correlation')
                audit['source_cells'] += len(cells)
                origin = snapshot['native_origin_cm']; unit = snapshot['native_unit_cm']
                size = snapshot['cell_size_units']; width = snapshot['grid_width']
                for key in unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(game):
                    raw = unreal.EcoCreatureInspectionLibrary.capture_agent(game, key)
                    if isinstance(raw, tuple): raw = next((v for v in raw if isinstance(v, str)), None)
                    agent = json.loads(raw) if raw else {}
                    if agent.get('region') != snapshot['region'] or agent.get('hp', 0) <= 0 or agent.get('last_intake', 0) <= 0: continue
                    position = agent.get('native_world_position')
                    if not position: continue
                    x, y = [max(0, min(width - 1, int((position[i] - origin[i]) / unit / size))) for i in (0, 1)]
                    cell = y * width + x
                    visual = cells.get(cell)
                    if not visual: continue  # Ungrounded or zero-capacity cells are intentionally unpublished.
                    audit['intake_samples'] += 1
                    pending = dict(elapsed=elapsed, native_step=snapshot['native_step'], cell=cell, agent=str(key),
                                   intake=agent['last_intake'], food=visual['source_food'], food_code=visual['food_code'])
                    anchors = snapshot.get('rendered_patch_anchors', [])
                    if anchors:
                        nearest = min(anchors, key=lambda a: sum((a['ground_cm'][i]-position[i])**2 for i in (0,1)))
                        pending['native_body_position_cm'] = position
                        pending['nearest_rendered_patch'] = nearest
                        pending['body_to_anchor_xy_cm'] = math.sqrt(sum((nearest['ground_cm'][i]-position[i])**2 for i in (0,1)))
                        # This is a location baseline, not a mouth/arrival verdict: S3 owns those tolerances.
                    previous = state.setdefault('feeding_previous', {}).get(cell)
                    if previous and previous['food_code'] != pending['food_code']:
                        audit['changes'].append(dict(cell=cell, previous=previous, current=pending))
                    state['feeding_previous'][cell] = pending
                    # Preserve a verified publication until its local renderer catches up.
                    audit['pending'].setdefault(cell, pending)
        if elapsed < state['next']: return
        state['next'] = elapsed + 2
        if visual_check:
            show = elapsed < 8 or elapsed >= 14
            if state.get('visual_show') != show:
                unreal.SystemLibrary.execute_console_command(game, 'eco.Grass.Visual ' + ('1' if show else '0'))
                state['visual_show'] = show
        if water_check:
            if 'water_region' not in state:
                habitats = [habitat for habitat in unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcoVegetationHabitat)
                            if habitat.get_editor_property('connected_fresh_water')]
                if not habitats:
                    raise RuntimeError('Authored connected water habitat required for water check')
                state['water_region'] = str(sorted(habitats, key=lambda habitat: habitat.get_path_name())[0].get_editor_property('region_id'))
            connected = elapsed < 8 or elapsed >= 34
            if state.get('water_connected') != connected:
                region = state['water_region']
                unreal.SystemLibrary.execute_console_command(game, f'eco.Grass.Water "{region}" ' + ('1' if connected else '0'))
                state['water_connected'] = connected
        for pawn in unreal.GameplayStatics.get_all_actors_of_class(game, unreal.Pawn):
            for cls in (unreal.EcoPlayerEcologyComponent, unreal.EcoThreatSourceComponent):
                for c in pawn.get_components_by_class(cls): c.set_editor_property('threat_enabled', False)
        phase = 'AuthoredCycle' if authored else ('Dry' if elapsed < duration / 2 else 'Rain')
        if grass_debug:
            if 'grass_region' not in state:
                available = sorted(str(field.get_editor_property('region_id')) for field in fields)
                state['grass_region'] = grass_region or available[0]
                if state['grass_region'] not in available:
                    raise RuntimeError('Requested grass debug region is absent')
            phase = 'Dry' if elapsed < duration * .4 else 'Rain' if elapsed < duration * .8 else 'Auto'
            if phase != state['phase']:
                region = state['grass_region']
                command = {'Dry': f'eco.Grass.Climate "{region}" 0 {dry_temperature}',
                           'Rain': f'eco.Grass.Climate "{region}" .5 20',
                           'Auto': f'eco.Grass.Auto "{region}"'}[phase]
                unreal.SystemLibrary.execute_console_command(game, command)
                state['phase'] = phase
        elif not authored and phase != state['phase']:
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
        for key in ([] if grass_profile else keys):
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
        if '-vegetationnetworkchildcoverage' in cmd.lower():
            # Explicit observer fixture: move server-owned viewers only. A regional
            # camera orbit around wolves does not necessarily cover a newborn's relevance bubble.
            region=('Forest','Barren','Highland')[int(elapsed/12)%3]
            live=[a for a in agents if a.get('region')==region and a.get('hp',0)>0 and a.get('native_world_position')]
            born=[a for a in live if a.get('species')=='Herbivore' and a.get('life',{}).get('origin')==1]
            wolves=[a for a in live if a.get('species')=='Wolf']
            candidates=born or wolves or live
            if candidates:
                target=min(candidates,key=lambda a:int(a['stable_id']));point=unreal.Vector(*target['native_world_position'])
                view=point+unreal.Vector(400,250,650)
                for controller in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.PlayerController):
                    viewer=controller.get_controlled_pawn()
                    if viewer:
                        viewer.set_actor_location(view,False,True)
                        controller.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(view,point))
                state['observer_targets'].append(dict(elapsed=elapsed,id=target['stable_id'],region=region,natural_child=bool(born)))
        pawn=unreal.GameplayStatics.get_player_pawn(game,0)
        camera=unreal.GameplayStatics.get_player_camera_manager(game,0)
        p=pawn.get_actor_location() if pawn else None;c=camera.get_camera_location() if camera else None
        native=next((n for n in unreal.ObjectIterator(unreal.EcoPolicyV3IntegratedSubsystem) if n.get_outer()==game),None)
        performance=json.loads(native.capture_step_performance()) if native else None
        sample = dict(elapsed=elapsed, world_seconds=unreal.GameplayStatics.get_time_seconds(game), phase=phase, fields=rows, authority_agents=len(keys), agents=agents,performance=performance,players=len(unreal.GameplayStatics.get_all_actors_of_class(game,unreal.PlayerController)),
            observer_pawn=[p.x,p.y,p.z] if p else None,observer_camera=[c.x,c.y,c.z] if c else None)
        if jwj_camera_check and 24 <= elapsed < 48 and elapsed - state['camera_changed'] >= .5 and c:
            sample.update(camera_region=state['camera_region'], camera_turn=state['camera_turn'],
                          observer_camera_yaw=camera.get_camera_rotation().yaw)
        state['rows'].append(sample)
        (out / (name + '_Progress.json')).write_text(json.dumps(state['rows'][-1], indent=2), encoding='utf-8')
        if pie:
            focus_region = state.get('grass_region', 'Forest')
            selected = next((f for f in fields if str(f.get_editor_property('region_id')) == focus_region), fields[0])
            plants = selected.get_editor_property('plants')
            count = plants.get_instance_count()
            if count and not jwj:
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
            if not grass_profile and count and state['shots'] < 3 and elapsed > 20 + state['shots'] * 40:
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

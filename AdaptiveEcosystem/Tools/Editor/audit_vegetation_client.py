"""Client-only received visual DTO and authority inspection; no simulation calls."""
import json, re, time, math
from pathlib import Path
import unreal
cmd = unreal.SystemLibrary.get_command_line()
match = re.search(r'-VegetationClientName=(\w+)', cmd)
if not match: raise RuntimeError('Client name required')
def arg(key,default):
    m=re.search(r'-'+key+r'=([^\s"]+)',cmd,re.I)
    return m.group(1) if m else default
folder=arg('VegetationAuditFolder','Vegetation_20261023')
duration=float(arg('VegetationClientDuration','26'))
visual_distance=float(arg('VegetationClientVisualDistance','-1'))
grass_travel = '-vegetationgrasstravelcheck' in cmd.lower()
if not math.isfinite(visual_distance) or not (-1 <= visual_distance <= 200000):
    raise RuntimeError('Client visual distance must be -1 (authored) or 0..200000 cm')
if not math.isfinite(duration) or not 20<=duration<=600:raise RuntimeError('Bounded client duration required')
if grass_travel and duration < 370:raise RuntimeError('Ten three-region circuits require at least 370 seconds')
map_name=arg('VegetationMap','LV_JYU_HerdMigration')
if map_name not in ('LV_JYU_HerdMigration','LV_JYU_Ecosystem','1102_Integration_JWJ','LV_JYU_IslandEcosystemRefreshed') or not re.fullmatch(r'[A-Za-z0-9_]+',folder):raise RuntimeError('Owned map/output folder required')
out = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / folder
out.mkdir(parents=True, exist_ok=True)
state = dict(start=None, next=0, samples=[],world=None,frame_ms=[],csv=False)
def tick(dt):
    # WorldPartition can load an inactive UWorld with the same map name. Name
    # alone is not a game-world identity; retain the world owning the local PC.
    game=state['world']
    if game is None or unreal.GameplayStatics.get_player_controller(game,0) is None:
        game=next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name()==map_name
            and unreal.GameplayStatics.get_player_controller(w,0) is not None
            and unreal.GameplayStatics.get_game_state(w) is not None),None)
        state['world']=game
    if not game: return
    if visual_distance >= 0 and not state.get('visual_distance_configured'):
        spawners = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcoCreatureIntegrationSpawner)
        if not spawners:
            return
        for spawner in spawners:
            spawner.set_editor_property('client_visual_distance', visual_distance)
        state['visual_distance_configured'] = True
    if state['start'] is None: state['start'] = time.monotonic()
    elapsed = time.monotonic() - state['start']
    if elapsed>5 and not state['csv']:
        unreal.SystemLibrary.execute_console_command(game,'csvprofile STARTFILE=EcosystemLife_'+folder+'_'+match.group(1)+'.csv')
        unreal.SystemLibrary.execute_console_command(game,'csvprofile START');state['csv']=True
    if elapsed>5 and math.isfinite(dt) and dt>0 and len(state['frame_ms'])<3600:state['frame_ms'].append(dt*1000)
    if elapsed < state['next']: return
    state['next'] = elapsed + 1
    fields = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.EcoVegetationField)
    rows=[]
    for field in fields:
        row=json.loads(field.capture_diagnostics());p=field.get_actor_location()
        row['actor_location']=[p.x,p.y,p.z]
        rows.append(row)
    visuals=[]
    for actor in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureRepresentationActor):
        if not actor.get_editor_property('bound'):continue
        v=actor.get_editor_property('visual_state')
        scale=actor.get_actor_scale3d()
        mesh=actor.get_editor_property('creature_mesh');asset=mesh.get_skeletal_mesh_asset();animation=mesh.get_anim_instance()
        visuals.append(dict(id=str(v.get_editor_property('stable_agent_id')),
            species=str(v.get_editor_property('species_id')),
            region=str(v.get_editor_property('region_id')),activity=str(v.get_editor_property('activity')),
            coat_tone=v.get_editor_property('coat_tone'),maturity=v.get_editor_property('maturity'),adult_visible=mesh.is_visible(),young_visible=actor.get_editor_property('immature_mesh').is_visible(),
            body_scale=v.get_editor_property('body_scale'),actor_scale=[scale.x,scale.y,scale.z],appearance=v.get_editor_property('appearance'),
            mesh=asset.get_path_name() if asset else None,animation=animation.get_class().get_name() if animation else None))
    camera=unreal.GameplayStatics.get_player_camera_manager(game,0)
    pawn=unreal.GameplayStatics.get_player_pawn(game,0)
    c=camera.get_camera_location() if camera else None;p=pawn.get_actor_location() if pawn else None
    sample = dict(elapsed=elapsed, fields=rows,visuals=visuals,
        observer_pawn=[p.x,p.y,p.z] if p else None,observer_camera=[c.x,c.y,c.z] if c else None)
    if grass_travel:
        partition = next((sub for sub in unreal.ObjectIterator(unreal.WorldPartitionSubsystem) if sub.get_outer()==game),None)
        sample['streaming_completed'] = partition.is_all_streaming_completed() if partition else None
        sample['landscape_proxies'] = sorted(a.get_path_name() for a in unreal.GameplayStatics.get_all_actors_of_class(game, unreal.LandscapeStreamingProxy))
        def distance(field):
            origin=field['actor_location']; size=field['grid_size_cm']
            return sum((cvalue - max(origin[i], min(origin[i]+size, cvalue)))**2 for i,cvalue in enumerate((c.x,c.y)))
        sample['nearest_region'] = min(rows,key=distance)['region'] if rows and c else None
    state['samples'].append(sample)
    if elapsed < duration: return
    ids = unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(game)
    best = max(state['samples'], key=lambda s: sum(f['instances'] for f in s['fields']))
    migration_subsystems=sum(s.get_outer()==game for s in unreal.ObjectIterator(unreal.EcoHerdMigrationSubsystem))
    candidates=[dict(path=w.get_path_name(),has_controller=unreal.GameplayStatics.get_player_controller(w,0) is not None,
        has_game_state=unreal.GameplayStatics.get_game_state(w) is not None) for w in unreal.ObjectIterator(unreal.World) if w.get_name()==map_name]
    result = dict(client=match.group(1), client_visual_distance_override_cm=visual_distance,
        authority_agents=len(ids), local_migration_subsystems=migration_subsystems,samples=state['samples'], best=best,
        observed_world=game.get_path_name(),same_named_worlds=candidates)
    frames=sorted(state['frame_ms'])
    if frames:result['rendered_frame_time']=dict(samples=len(frames),p95_ms=frames[max(0,math.ceil(len(frames)*.95)-1)],max_ms=frames[-1])
    native=next((n for n in unreal.ObjectIterator(unreal.EcoPolicyV3IntegratedSubsystem) if n.get_outer()==game),None)
    if native is not None:result['native_performance']=json.loads(native.capture_step_performance())
    result['scale_payload_matches_actor']=all(abs(v['body_scale']-v['actor_scale'][0])<1e-5 for s in state['samples'] for v in s['visuals'])
    result['received_visual_ids']=sorted({v['id'] for s in state['samples'] for v in s['visuals']})
    result['received_appearances']=sorted({v['appearance'] for s in state['samples'] for v in s['visuals']})
    result['morph_matches_payload']=all(v['appearance']==0 or (v['animation'] and v['mesh'] and
        ('SK_DeerStag' in v['mesh'] if v['appearance']==1 else 'SK_DeerDoe' in v['mesh']))
        for s in state['samples'] for v in s['visuals'] if v['species'] == 'Herbivore')
    result['passed'] = len(ids)==0 and migration_subsystems==0 and len(best['fields'])>0 and all(not f['authority'] for f in best['fields']) and sum(f['instances'] for f in best['fields'])>0 and result['scale_payload_matches_actor']
    if map_name in ('LV_JYU_Ecosystem', 'LV_JYU_IslandEcosystemRefreshed'):
        result['passed']=result['passed'] and bool(result['received_visual_ids']) and result.get('native_performance',{}).get('native_steps_total',-1)==0
        if any(f.get('natural_profile','None')!='None' for f in best['fields']):result['passed']=result['passed'] and result['morph_matches_payload']
    if grass_travel:
        visits=[]
        for sample in state['samples']:
            if sample['nearest_region'] and (not visits or visits[-1]['region'] != sample['nearest_region']):
                visits.append(dict(region=sample['nearest_region'],elapsed=sample['elapsed']))
        additions=sum(len(set(b['landscape_proxies'])-set(a['landscape_proxies'])) for a,b in zip(state['samples'],state['samples'][1:]))
        removals=sum(len(set(a['landscape_proxies'])-set(b['landscape_proxies'])) for a,b in zip(state['samples'],state['samples'][1:]))
        regions=sorted({f['region'] for s in state['samples'] for f in s['fields']})
        limits={region:max(f['local_candidate_limit'] for s in state['samples'] for f in s['fields'] if f['region']==region) for region in regions}
        checks=dict(ten_visits_per_region=all(sum(v['region']==r for v in visits)>=10 for r in regions) and len(regions)==3,
            terrain_loaded_and_unloaded=additions>0 and removals>0,
            streaming_settled=any(s['streaming_completed'] for s in state['samples']),
            near_and_coarse=any(f['near_instances']>0 for s in state['samples'] for f in s['fields']) and any(f['coarse_instances']>0 for s in state['samples'] for f in s['fields']),
            bounded_cache=all(f['cached_candidates']<=limits[f['region']] and f['instances']<=f['cached_candidates'] for s in state['samples'] for f in s['fields']))
        result['grass_travel']=dict(checks=checks,visits=visits,landscape_additions=additions,landscape_removals=removals,
            candidate_limits=limits,scope='Existing authority observer cycle; no direct client pawn, creature or food writes')
        result['passed']=result['passed'] and all(checks.values())
    (out / (match.group(1)+'_Client.json')).write_text(json.dumps(result,indent=2), encoding='utf-8')
    if state['csv']:unreal.SystemLibrary.execute_console_command(game,'csvprofile STOP')
    unreal.log('VEGETATION_CLIENT_FINISHED '+json.dumps(dict(client=match.group(1),passed=result['passed'])))
    unreal.unregister_slate_post_tick_callback(handle)
handle = unreal.register_slate_post_tick_callback(tick)

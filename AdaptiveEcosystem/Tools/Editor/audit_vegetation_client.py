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
if not math.isfinite(duration) or not 20<=duration<=600:raise RuntimeError('Bounded client duration required')
map_name=arg('VegetationMap','LV_JYU_HerdMigration')
if map_name not in ('LV_JYU_HerdMigration','LV_JYU_Ecosystem') or not re.fullmatch(r'[A-Za-z0-9_]+',folder):raise RuntimeError('Owned map/output folder required')
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
        visuals.append(dict(id=str(v.get_editor_property('stable_agent_id')),
            region=str(v.get_editor_property('region_id')),activity=str(v.get_editor_property('activity')),
            body_scale=v.get_editor_property('body_scale'),actor_scale=[scale.x,scale.y,scale.z]))
    camera=unreal.GameplayStatics.get_player_camera_manager(game,0)
    pawn=unreal.GameplayStatics.get_player_pawn(game,0)
    c=camera.get_camera_location() if camera else None;p=pawn.get_actor_location() if pawn else None
    state['samples'].append(dict(elapsed=elapsed, fields=rows,visuals=visuals,
        observer_pawn=[p.x,p.y,p.z] if p else None,observer_camera=[c.x,c.y,c.z] if c else None))
    if elapsed < duration: return
    ids = unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(game)
    best = max(state['samples'], key=lambda s: sum(f['instances'] for f in s['fields']))
    migration_subsystems=sum(s.get_outer()==game for s in unreal.ObjectIterator(unreal.EcoHerdMigrationSubsystem))
    candidates=[dict(path=w.get_path_name(),has_controller=unreal.GameplayStatics.get_player_controller(w,0) is not None,
        has_game_state=unreal.GameplayStatics.get_game_state(w) is not None) for w in unreal.ObjectIterator(unreal.World) if w.get_name()==map_name]
    result = dict(client=match.group(1), authority_agents=len(ids), local_migration_subsystems=migration_subsystems,samples=state['samples'], best=best,
        observed_world=game.get_path_name(),same_named_worlds=candidates)
    frames=sorted(state['frame_ms'])
    if frames:result['rendered_frame_time']=dict(samples=len(frames),p95_ms=frames[max(0,math.ceil(len(frames)*.95)-1)],max_ms=frames[-1])
    native=next((n for n in unreal.ObjectIterator(unreal.EcoPolicyV3IntegratedSubsystem) if n.get_outer()==game),None)
    if native is not None:result['native_performance']=json.loads(native.capture_step_performance())
    result['scale_payload_matches_actor']=all(abs(v['body_scale']-v['actor_scale'][0])<1e-5 for s in state['samples'] for v in s['visuals'])
    result['received_visual_ids']=sorted({v['id'] for s in state['samples'] for v in s['visuals']})
    result['passed'] = len(ids)==0 and migration_subsystems==0 and len(best['fields'])>0 and all(not f['authority'] for f in best['fields']) and sum(f['instances'] for f in best['fields'])>0 and result['scale_payload_matches_actor']
    if map_name=='LV_JYU_Ecosystem':
        result['passed']=result['passed'] and bool(result['received_visual_ids']) and result.get('native_performance',{}).get('native_steps_total',-1)==0
    (out / (match.group(1)+'_Client.json')).write_text(json.dumps(result,indent=2), encoding='utf-8')
    if state['csv']:unreal.SystemLibrary.execute_console_command(game,'csvprofile STOP')
    unreal.log('VEGETATION_CLIENT_FINISHED '+json.dumps(dict(client=match.group(1),passed=result['passed'])))
    unreal.unregister_slate_post_tick_callback(handle)
handle = unreal.register_slate_post_tick_callback(tick)

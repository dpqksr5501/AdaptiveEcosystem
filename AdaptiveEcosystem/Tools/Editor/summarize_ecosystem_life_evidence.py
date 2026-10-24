"""Summarize actual saved reports; never manufactures a missing validation result."""
import csv,hashlib,json,math,re,shutil
from collections import Counter,defaultdict
from pathlib import Path

root=Path(__file__).resolve().parents[2]
saved=root/'Saved/EcosystemLife_20261023'
evidence=root/'Docs/Architecture/Evidence'
evidence.mkdir(parents=True,exist_ok=True)

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def stats(values):
    values=sorted(values)
    return dict(samples=len(values),p95=values[max(0,math.ceil(len(values)*.95)-1)],max=values[-1]) if values else None
def food_error(rows):
    return max((abs(f[a]-f[b]) for r in rows for f in r['fields'] for a,b in
        (('food','ledger_amount'),('consumed','ledger_consumed'),('grown','ledger_grown'),('environment_lost','ledger_environment_lost'))),default=0)

def experiment(name):
    d=read(saved/(name+'_Life.json'))
    if d['result']!='FINISHED':raise AssertionError(name+' did not finish')
    rows=d['samples'];end=rows[-1];individuals={};previous={};role_motion=Counter();cooperative=0;transfers=0;meat_error=0;role_changes=0;role_switches=0;plans={}
    for r in rows:
        targets=defaultdict(set)
        for a in r['agents']:
            identity=a['stable_id'];life=a.get('life',{});individuals[identity]=a
            if a.get('migration_plan',0)>0 and a.get('migration_state'):plans[str(a['migration_plan'])]={k:a.get(k) for k in ('migration_state','migration_destination','migration_arrived','migration_members')}
            meat_error=max(meat_error,abs(life.get('meat_issued',0)-life.get('meat_consumed',0)-life.get('meat_wasted',0)-life.get('meat_remaining',0)))
            if life.get('role_target','0')!='0':targets[(a['region'],life.get('role_target'))].add(life.get('role'))
            old=previous.get(identity)
            if old:
                transfers+=old['region']!=a['region']
                old_role=old.get('life',{}).get('role',0);new_role=life.get('role',0)
                role_changes+=old_role!=new_role
                role_switches+=old_role in (1,2) and new_role in (1,2) and old_role!=new_role
                if a.get('native_world_position') and old.get('native_world_position'):
                    distance=math.dist(a['native_world_position'][:2],old['native_world_position'][:2])
                    if distance>20:role_motion[str(life.get('role',0))]+=1
            previous[identity]=a
        cooperative+=sum(1 in roles and 2 in roles for roles in targets.values())
    generations=defaultdict(list)
    for a in individuals.values():generations[a.get('life',{}).get('generation',0)].append(a)
    cohort=[]
    for generation,agents in sorted(generations.items()):
        genes=[a['life'] for a in agents if 'life' in a]
        cohort.append(dict(generation=generation,observed_individuals=len(agents),
            mean_speed_gene=sum(g['speed_gene'] for g in genes)/len(genes) if genes else None,
            mean_size_gene=sum(g['size_gene'] for g in genes)/len(genes) if genes else None,
            observed_offspring_contributions=sum(g['offspring'] for g in genes)))
    return dict(name=name,seed=d.get('seed'),ecosystem_life_enabled=d.get('ecosystem_life_enabled'),
        fixed_step_benchmark=d.get('fixed_step_benchmark'),finished=True,requested_simulation_seconds=d.get('fixed_step_simulation_target'),
        last_observed_simulation_seconds=end.get('simulation_elapsed'),observation_wall_seconds=end.get('elapsed'),
        fixture=d.get('fixture'),alive_last_sample=sum(a.get('hp',0)>0 for a in end['agents']),
        peak_alive_sampled=max(sum(a.get('hp',0)>0 for a in r['agents']) for r in rows),
        living_species=dict(Counter(a['species'] for a in end['agents'] if a.get('hp',0)>0)),observed_natural_children=len(d['natural_child_ids']),
        generations=cohort,region_transfers_observed=transfers,roles_with_movement_samples=dict(role_motion),
        simultaneous_lead_intercept_samples=cooperative,hunting_role_transitions=role_changes,lead_intercept_switches=role_switches,
        migration_plans_last_observed=plans,food_audit_max_error=food_error(rows),meat_audit_max_error=meat_error,
        performance_last_sample=end['performance'],final_regions=[dict(region=f['region'],food=f['food'],moisture=f['mean_moisture']) for f in end['fields']])

def csv_stats(path):
    values=defaultdict(list)
    with path.open(newline='',encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            for key in ('GameThreadTime','RenderThreadTime','FrameTime','PhysicalUsedMB'):
                try:value=float(row[key])
                except (KeyError,ValueError,TypeError):continue
                if math.isfinite(value) and value>=0:values[key].append(value)
            # Dedicated CSV does not publish GameThreadTime. Keep this derived
            # sum separate: measured exclusive GT scopes, excluding wait scopes.
            scopes=[]
            for key,raw in row.items():
                if not key or not key.startswith('Exclusive/GameThread/') or '/EventWait/' in key:continue
                try:value=float(raw)
                except (ValueError,TypeError):continue
                if math.isfinite(value) and value>=0:scopes.append(value)
            if scopes:values['InstrumentedGameThreadNonWaitScopesMs'].append(sum(scopes))
    return {key:stats(v) for key,v in values.items()}

def network(folder):
    p=root/'Saved'/folder;server=read(p/'Server_Runtime.json');relevance=read(p/'Relevance.json')
    if server['result']!='FINISHED' or not relevance['passed']:raise AssertionError(folder+' incomplete')
    clients={}
    for name in ('ClientA','ClientB'):
        d=read(p/(name+'_Client.json'))
        if not d['passed']:raise AssertionError(name+' failed')
        clients[name]=dict(authority_agents=d['authority_agents'],migration_subsystems=d['local_migration_subsystems'],
            native=d.get('native_performance'),scale_matches=d['scale_payload_matches_actor'],received_creatures=len(d['received_visual_ids']),
            rendered_frame_time=d.get('rendered_frame_time'))
    rates={key:[] for key in ('net_received_bytes_per_second','net_sent_bytes_per_second')}
    for before,after in zip(server['samples'],server['samples'][1:]):
        seconds=after['elapsed']-before['elapsed']
        if seconds<=0:continue
        for key,total in (('net_received_bytes_per_second','net_received_total_bytes'),('net_sent_bytes_per_second','net_sent_total_bytes')):
            if total not in before.get('performance',{}) or total not in after.get('performance',{}):continue
            delta=after['performance'][total]-before['performance'][total]
            if delta>=0:rates[key].append(delta/seconds)
    return dict(folder=folder,relevance=relevance,clients=clients,food_audit_max_error=food_error(server['samples']),
        authority_last_performance=server['samples'][-1].get('performance'),
        observed_net_rate_bytes_per_second={key:stats(values) for key,values in rates.items()},
        net_rate_method='Cumulative NetDriver total byte differences / actual observer wall seconds; monotonic intervals only. Direct Driver *BytesPerSecond counters remained zero in this capture and are not a traffic measurement.',
        csv={name:csv_stats(root/'Saved/Profiling/CSV'/('EcosystemLife_'+folder+'_'+name+'.csv')) for name in ('Server','ClientA','ClientB')})

def checkpoint(name):
    d=read(saved/(name+'_Life.json'))
    if d['result']!='FINISHED' or not d['operation']:raise AssertionError(name+' incomplete')
    return dict(result=d['result'],operation=d['operation'],food_audit_max_error=food_error(d['samples']))

def encounter(name):
    d=read(saved/('Encounter_'+name+'.json'))
    if d['result']!='FINISHED':raise AssertionError(name+' incomplete')
    rows=d['samples'];mem=[r['agent']['life'] for r in rows]
    return dict(subject=d['subject'],samples=len(rows),strike_requests=d.get('strike_requests',0),
        minimum_hp=min(r['agent']['hp'] for r in rows),maximum_actual_player_speed=max(r['player_speed'] for r in rows),
        peak_memory={k:max(m[k] for m in mem) for k in ('familiarity','curiosity','fear','hostility','unknown_fear')},
        encounter_kinds=sorted({m['last_encounter'] for m in mem}),responses=sorted({m['response'] for m in mem}),checkpoint=d.get('checkpoint'))

automation=read(saved/'AutomationFinal/index.json')
report=dict(schema=2,map='/Game/JYU/Maps/LV_JYU_Ecosystem',profile='soil-v1 + ecosystem-life-v1 opt-in; SocialControl=0',
    policy='V1 7/4, v3 18/5 mask2 and optional21 unchanged; existing weights; rules overlay, no retraining',
    automation={k:automation[k] for k in ('succeeded','succeededWithWarnings','failed','notRun')},
    soil_parity=read(saved/'SoilParity.json'),asset_reload=read(saved/'AssetReload.json'),
    runtime_dependencies=read(saved/'RuntimeDependencies.json'))
if report['automation']['failed'] or report['automation']['notRun']:raise AssertionError('Automation gate failed')
if not all(report[k].get('passed') for k in ('soil_parity','asset_reload','runtime_dependencies')):raise AssertionError('Parity/asset gate failed')
report['experiments']=[experiment(name) for name in ('FinalExtended11','FinalExtended23','FinalExtended47','FinalOn23_600','FinalOff23')]
report['migration_drought_fixture']=experiment('FinalDrought23')
if report['migration_drought_fixture']['region_transfers_observed']<=0:raise AssertionError('Drought fixture did not exercise actual region handoff')
report['pre_reserve_fix_experiments']='LongSeed*/Extended* are historical, including free adult reserve at birth; excluded from final biological conclusions'
report['checkpoints']={name:checkpoint(name) for name in ('FinalSave','FinalLoad','RecoveryLoad','EncounterLoad')}
report['encounters']={name:encounter(name) for name in ('harmless','ambush','chase')}
recovery=read(saved/'Recovery.json')
if recovery['result']!='FINISHED':raise AssertionError('Recovery incomplete')
report['recovery']=dict(result=recovery['result'],initial_wolf_ids=recovery['initial_wolf_ids'],strike_requests=recovery['strike_requests'],checkpoint=recovery['checkpoint'])
pie=read(saved/'PIE_Runtime.json')
if pie['result']!='FINISHED' or not pie['child_visuals']:raise AssertionError('Actual child visual evidence missing')
report['pie']=dict(result=pie['result'],seconds=pie['duration_wall_seconds'],screenshots=pie['screenshots'],
    food_audit_max_error=food_error(pie['samples']),child_visual_samples=len(pie['child_visuals']),
    child_ids=sorted({c['id'] for c in pie['child_visuals']}),child_scale_range=[min(c['actor_scale'] for c in pie['child_visuals']),max(c['actor_scale'] for c in pie['child_visuals'])],
    animation_classes=sorted({c['animation'] for c in pie['child_visuals']}),max_ik_alpha=max(c['ik_alpha'] for c in pie['child_visuals']))
report['network']=[network('EcosystemLifeConcurrent_20261023')]
report['earlier_network_reference']='EcosystemLifeNetwork_20261023 contains earlier successive late-join coverage; final metrics use the current concurrent run only'
builds=sorted((root/'Saved/IntegrationBuilds').glob('Milestone_Final_*.log'),key=lambda p:p.stat().st_mtime)
report['latest_editor_build']=builds[-1].name
report['verification_scopes']={
    'long_runs_pie_concurrent_network':'Milestone_Final_20261023_230551.log',
    'automation_checkpoints_drought_and_package':report['latest_editor_build'],
    'changes_after_long_scene_validation':'Editor-only FacingArrow template creation, its regression test, and asset-label cook configuration; Native life/movement/replication code unchanged'}
for key,file in (('game_build','GameBuild.log'),('package','Package.log'),('packaged_smoke','PackagedSmoke.log')):
    text=(saved/file).read_text(encoding='utf-8-sig',errors='replace')
    passed=('Result: Succeeded' in text) if key=='game_build' else ('BUILD SUCCESSFUL' in text) if key=='package' else ('Test duration completed; Ready=1' in text and 'Authority ready:' in text)
    if key=='packaged_smoke':passed=passed and not re.search(r'Runtime stopped|Fatal error|Accessed None|Log\w+: Error:|Failed to find object.*(?:Rain_System|NS_Blizzard|A_Rain_Cue)',text)
    report[key]=dict(log=file,passed=passed)
    if not passed:raise AssertionError(key+' incomplete/failed')
referenced=root/'Saved/Cooked/Windows/AdaptiveEcosystem/Metadata/ReferencedSet.txt'
referenced_packages=set(referenced.read_text(encoding='utf-8-sig').lower().splitlines())
required=report['runtime_dependencies']['dependencies']+['/Game/JYU/Ecosystem/BP_JYU_AuthoredSpring']
report['cooked_runtime_dependencies']={path:path.lower() in referenced_packages for path in required}
if not all(report['cooked_runtime_dependencies'].values()):raise AssertionError('Runtime dependency missing from cooked registry')
packaged_images=sorted((root/'Saved/EcosystemLifePackage/Windows/AdaptiveEcosystem/Saved/Screenshots').rglob('*.png'),key=lambda p:p.stat().st_mtime)
if not packaged_images:raise AssertionError('Packaged rendered screenshot missing')
shutil.copyfile(packaged_images[-1],evidence/'EcosystemLife_Packaged_20261023.png')
report['packaged_smoke']['rendered_image']='EcosystemLife_Packaged_20261023.png'
report['packaged_smoke']['fixture']='Development executable, D3D11 1280x720, NoSound, observer pawn cycle, 90 seconds; no Python observer/inference'
for i in (0,2):
    source=saved/('VegetationPIE_'+str(i)+'.png')
    shutil.copyfile(source,evidence/('EcosystemLife_PIE_'+str(i)+'_20261023.png'))
report['limits']=['No full-life Python trajectory parity or new weights','Uniform scale only; no authored morph/bone proportions',
    'Observed cohorts are not proof of beneficial selection or equilibrium','Measured at this scene population, not 500/1000 creatures',
    'Same-build startup restore only; no cross-build migration or live rollback','Prototype plant shapes and movement marks; no bone-accurate footprint art',
    'No complete MMO service, player persistence, quest or loot economy implementation']
destination=evidence/'EcosystemLife_20261023.json'
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(evidence=str(destination),automation=report['automation'],experiments=[{k:e[k] for k in ('name','last_observed_simulation_seconds','alive_last_sample','observed_natural_children')} for e in report['experiments']]),ensure_ascii=False))

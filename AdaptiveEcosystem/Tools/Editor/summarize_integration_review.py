"""Compact post-review evidence, tied to the completed build and real UE reports."""
import json,re,shutil
from pathlib import Path

root=Path(__file__).resolve().parents[2]
raw=root/'Saved/IntegrationReview_20261023'
dest=root/'Docs/Architecture/Evidence'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
build=root/'Saved/IntegrationBuilds/Milestone_Final_20261023_154448.log'
assert 'Result: Succeeded' in build.read_text(encoding='utf-8',errors='replace')
automation=read(raw/'Automation02/index.json')
assert automation['failed']==automation['notRun']==automation['inProcess']==0
assert automation['succeeded']+automation['succeededWithWarnings']==213
tests=[t for t in automation['tests'] if t['fullTestPath'].startswith('AdaptiveEcosystem.Review.')]
assert len(tests)==4 and all(t['state']=='Success' for t in tests)
assets=read(raw/'AssetReload.json')
assert assets['passed'] and len(assets['b_blueprints'])==6 and not assets['legacy_visual_weather']
assert assets['routes'] and all(r['valid'] for r in assets['routes'])

def runtime(name):
    d=read(raw/(name+'_Runtime.json'));ss=d['samples'];ff=[f for s in ss for f in s['fields']]
    assert d['result']=='FINISHED' and not d['error'] and ss
    errors={a:max(abs(f[a]-f[b]) for f in ff) for a,b in (
        ('food','ledger_amount'),('consumed','ledger_consumed'),('grown','ledger_grown'),('environment_lost','ledger_environment_lost'))}
    assert max(errors.values())<1.e-6
    log=(raw/(name+'.log')).read_text(encoding='utf-8',errors='replace')
    assert not re.search('Runtime stopped|receipt rejected|VEGETATION_AUDIT_ERROR|Unsupported authoring|Accessed None|NULL AttachComponent',log)
    return dict(result=d['result'],fixture=d['fixture'],observed_seconds=ss[-1]['elapsed'],samples=len(ss),
        max_ledger_errors=errors,final_population=ss[-1]['authority_agents'],final_fields=ss[-1]['fields'],
        actual_intake_samples=sum(a.get('last_intake',0)>0 for s in ss for a in s['agents']),
        active_journey_samples=sum(a.get('migration_active',False) for s in ss for a in s['agents']),
        region_transfers=d['region_transfers'],screenshots=d['screenshots'])

pie=runtime('PIE01');server=runtime('Server')
transfer_ids={t['id'] for t in server['region_transfers'] if t['destination']=='Forest'}
clients=[]
for name in ('ClientA','ClientB'):
    d=read(raw/(name+'_Client.json'));log=(raw/(name+'.log')).read_text(encoding='utf-8',errors='replace')
    zero_step=bool(re.search(r'NetMode=3 LogicalOwned=0 .* Step=0',log))
    assert d['passed'] and d['authority_agents']==d['local_migration_subsystems']==0 and zero_step
    assert d['best']['fields'] and all(not f['authority'] for f in d['best']['fields'])
    clients.append(dict(name=name,passed=True,authority_agents=0,local_migration_subsystems=0,zero_native_step=True,
        fields=d['best']['fields'],received_migrated_forest_ids=sorted({v['id'] for s in d['samples'] for v in s['visuals']
            if v['region']=='Forest' and v['id'] in transfer_ids})))
processes=read(raw/'NetworkProcesses.json')
assert len(processes)==3 and all(p['ExitCode']==0 for p in processes)
relevance=read(raw/'Relevance.json');assert relevance['passed']
relevance_roundtrip=read(root/'Saved/IntegrationReviewNet_20261023/Relevance.json');assert relevance_roundtrip['passed']
negative_guard=read(raw/'RelevanceNegativeGuard.json');assert negative_guard['passed']
server_log=(raw/'Server.log').read_text(encoding='utf-8',errors='replace')
completed=[dict(plan=int(p),herd=int(h),origin=o,destination=d,arrived=int(a),members=int(m)) for p,h,o,d,a,m in re.findall(
    r'\[HerdMigration\] Plan=(\d+) Herd=(\d+) State=Settled Reason=JourneyComplete From=(\w+) To=(\w+) Arrived=(\d+)/(\d+)',server_log)]
engine=read(raw/'EngineFree.json')
assert len(engine['runs'])==12 and max(r['max_step_balance_error'] for r in engine['runs'])<1.e-9
report=dict(date='2026-10-23',baseline_head='ecfd82fab04d16531ae7e00a2adaf3a4737d2fcf',branch='codex/social-shelter-handoff',dirty=True,
    scope='Implemented Native/M4/vegetation/authoring/migration/representation and client boundaries; not every planned ecosystem feature',
    build=dict(succeeded=True,log=str(build.relative_to(root))),
    automation={k:automation[k] for k in ('succeeded','succeededWithWarnings','failed','notRun','totalDuration')},
    regression_tests=[dict(name=t['fullTestPath'],state=t['state']) for t in tests],
    saved_assets=dict(blueprints=6,weather_actors=len(assets['weather']),habitat_actors=len(assets['habitats']),routes=assets['routes']),
    pie=pie,server=server,clients=clients,
    relevance=relevance,additional_region_roundtrip=relevance_roundtrip,relevance_fault_injection=negative_guard,
    client_world_identity=[dict(name=name,world=read(raw/(name+'_Client.json'))['observed_world'],
        same_named_worlds=len(read(raw/(name+'_Client.json'))['same_named_worlds']),
        active_candidates=[c for c in read(raw/(name+'_Client.json'))['same_named_worlds'] if c['has_controller'] and c['has_game_state']],
        inactive_examples=[c for c in read(raw/(name+'_Client.json'))['same_named_worlds'] if not c['has_controller']][:2]) for name in ('ClientA','ClientB')],
    full_server_log=dict(seconds=270,completed_plans=completed,completion_may_include_dead_members=True),
    processes=[dict(name=p['Name'],exit=p['ExitCode']) for p in processes],engine_free=engine,
    fixes=['Regional entry is counted once; outstanding plans reserve only living members outside the destination; current receipt deltas bridge the population commit',
        'Shared route validator rejects non-finite/degenerate/unbounded paths before terrain and debug consumers; direct native sweep is bounded',
        'Collapsed/zero habitat bounds cannot supply an unbounded axis; invalid regional habitats are rejected before gathering',
        'Invalid ON soil layout cannot silently regenerate using the OFF world or index absent arrays',
        'Network observation times reject NaN/infinity and observer durations beyond the normal server exit',
        'Runtime observers retain a game world owning GameState/local PlayerController; a same-named inactive WorldPartition UWorld cannot replace it',
        'Near-field delivery is checked over camera transitions; a preserved peak count cannot hide missing fields/camera'],
    preflight_negative_cases=['NaN duration rejected before process start','Observer duration beyond exit rejected before process start','Infinite exit rejected before process start'],
    validation_notes=['Automation01 contained one new test fixture failure (missing route actor). Fixed fixture and reran the entire suite as Automation02.',
        'Unreal process exit 0 did not imply test success; final acceptance uses exported JSON failed/notRun/inProcess counts.',
        'Initial 18-second and reproduced 26-second apparent client gaps came from name-only UWorld selection; the wrong world also had no camera. Preserved InitialClientA_18s.json/log and WrongWorldClientA_26s.json/Relevance.json. Fixed world selection, then repeated the same 30-second join and 190-second late join with continuous near-field/camera validation.',
        'Earlier weather-controls PIE remains historical evidence; this review does not change weather presentation or policy schema/weights.'],
    remaining=['Full ecosystem roadmap C-G is not complete; see implementation status',
        'No complete ecosystem save/restore, cook/package, Python ON-world parity/retraining or measured server/client p95 and bandwidth',
        'No verified connected water scene; dedicated riparian/shrub meshes and vegetation cover sensing remain open',
        'Recovery forecasting and limited place knowledge remain future migration extensions',
        'A journey that cannot return still needs an explicit recovery/termination contract preserving native out-of-stage guards; no teleport fix introduced',
        'All deer die by 600s in the distinct flat engine-free baseline; short integrated success does not prove ecological equilibrium',
        'Inherited HLOD/Editor AnimGraph load and NavMesh warnings require packaging/performance follow-up'])
dest.mkdir(parents=True,exist_ok=True)
(dest/'IntegrationReview_20261023.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(raw/'VegetationPIE_2.png',dest/'IntegrationReview_PIE_20261023.png')
print(json.dumps(dict(automation=report['automation'],ledger_errors=server['max_ledger_errors'],
    transfers=len(server['region_transfers']),completed_plans=len(completed),
    late_client_received_ids=clients[-1]['received_migrated_forest_ids']),ensure_ascii=False,indent=2))

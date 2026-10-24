"""Summarize fresh UE/native reports without treating unevaluated gates as passes."""
import json, re
from pathlib import Path
root = Path(__file__).resolve().parents[2]
raw = root / 'Saved/Vegetation_20261023'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def runtime(name):
    data = read(raw / (name + '_Runtime.json'))
    samples = data['samples']
    fields = [f for sample in samples for f in sample['fields']]
    last_dry = next(s for s in reversed(samples) if s['phase']=='Dry')
    last = samples[-1]
    regions = {}
    for f in last['fields']:
        dry = next(d for d in last_dry['fields'] if d['region']==f['region'])
        regions[f['region']] = dict(final_food=f['food'], consumed=f['consumed'], grown=f['grown'],
            environment_lost=f['environment_lost'], habitat_removed=f['ledger_habitat_removed'],
            dry_moisture=dry['mean_moisture'], final_rain_moisture=f['mean_moisture'],
            visual_cells=f['visual_cells'], instances=f['instances'])
    return dict(result=data['result'], error=data['error'], fixture=data['fixture'], sample_count=len(samples),
        observed_wall_seconds=last['elapsed'], observed_world_seconds=last['world_seconds'],
        final_population=last['authority_agents'], regions=regions,
        max_grid_ledger_error=max(abs(f['food']-f['ledger_amount']) for f in fields),
        max_consumed_ledger_error=max(abs(f['consumed']-f['ledger_consumed']) for f in fields),
        max_growth_ledger_error=max(abs(f['grown']-f['ledger_grown']) for f in fields),
        max_environment_loss_ledger_error=max(abs(f['environment_lost']-f['ledger_environment_lost']) for f in fields),
        actual_intake_samples=sum(a.get('last_intake',0)>0 for s in samples for a in s['agents']),
        active_journey_samples=sum(a.get('migration_active',False) for s in samples for a in s['agents']),
        region_transfers=data.get('region_transfers',[]), screenshots=data['screenshots'])
automation = read(raw / 'Automation02/index.json')
engine_free = read(raw / 'EngineFree.json')
builds = sorted((root / 'Saved/IntegrationBuilds').glob('Milestone_A_*.log'))
last_build = builds[-1]
report = dict(date='2026-10-23', baseline_head='ecfd82fab04d16531ae7e00a2adaf3a4737d2fcf',
    branch='codex/social-shelter-handoff', dirty=True, policy_weights_changed=False, python_retraining=False,
    build=dict(log=str(last_build.relative_to(root)), succeeded='Result: Succeeded' in last_build.read_text(encoding='utf-8',errors='replace')),
    automation={k:automation[k] for k in ('succeeded','succeededWithWarnings','failed','notRun','totalDuration')},
    pie=runtime('PIE04'), server=runtime('Server'), engine_free=engine_free,
    limitations=['PIE04 preceded final habitat validation only; final network/automation use final build',
        'Visuals are <=256 exact cell samples per region, not complete vegetation coverage; no dry-color material hookup',
        'Authored water geometry validated; no water-volume scene acceptance yet',
        'No Python ON-world parity, retraining, complete ecosystem save/restore or cook/packaging',
        'No server/client p95, memory/bandwidth benchmark or long integrated multi-seed ecological balance',
        'Engine-free baseline is a different flat world with no terrain/Social/integrated wild configuration; all deer extinct at 600s in these 12 runs',
        'Experiences, trace investigation, conditional birth/genome/body pipeline and remaining plan items remain open'])
report['clients'] = []
for name in ('ClientA','ClientB'):
    client = read(raw / (name + '_Client.json'))
    text = (raw / (name + '.log')).read_text(encoding='utf-8',errors='replace')
    report['clients'].append(dict(name=name, passed=client['passed'], authority_agents=client['authority_agents'],
        received_fields=client['best']['fields'], log_client_zero_step=bool(re.search(r'NetMode=3 LogicalOwned=0 .* Step=0',text))))
assert report['build']['succeeded'] and not report['automation']['failed'] and not report['automation']['notRun']
for name in ('pie','server'):
    assert report[name]['result']=='FINISHED' and report[name]['max_grid_ledger_error']<1.e-6
assert all(c['passed'] and c['authority_agents']==0 and c['log_client_zero_step'] for c in report['clients'])
dest = root / 'Docs/Architecture/Evidence/Vegetation_20261023.json'
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(evidence=str(dest),automation=report['automation'],pie=report['pie']['regions'],
    server_population=report['server']['final_population'],clients=[dict(name=c['name'],passed=c['passed']) for c in report['clients']]),ensure_ascii=False,indent=2))

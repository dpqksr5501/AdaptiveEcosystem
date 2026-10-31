"""Publish compact evidence from the saved BP map; never fabricate missing gates."""
import json
import re
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[2]
raw = root / 'Saved/EcosystemBP_20261023'
dest = root / 'Docs/Architecture/Evidence'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def summarize_runtime(name):
    data = read(raw / (name + '_Runtime.json'))
    samples = data['samples']
    fields = [f for s in samples for f in s['fields']]
    regions = {}
    for final in samples[-1]['fields']:
        rows = [f for f in fields if f['region'] == final['region']]
        regions[final['region']] = dict(
            final=final,
            rain_range=[min(f['rain'] for f in rows), max(f['rain'] for f in rows)],
            moisture_range=[min(f['mean_moisture'] for f in rows), max(f['mean_moisture'] for f in rows)],
            food_range=[min(f['food'] for f in rows), max(f['food'] for f in rows)],
            instance_range=[min(f['instances'] for f in rows), max(f['instances'] for f in rows)])
    errors = {a: max(abs(f[a] - f[b]) for f in fields) for a, b in (
        ('food', 'ledger_amount'), ('consumed', 'ledger_consumed'),
        ('grown', 'ledger_grown'), ('environment_lost', 'ledger_environment_lost'))}
    assert data['result'] == 'FINISHED' and not data['error']
    assert max(errors.values()) < 1.e-6
    assert all(r['rain_range'][1] > .6 and r['rain_range'][0] < .01 for r in regions.values())
    assert all(f['visual_class'].startswith('/Game/JYU/Ecosystem/BP_JYU_VegetationField.') for f in fields)
    return dict(result=data['result'], fixture=data['fixture'], samples=len(samples),
        observed_wall_seconds=samples[-1]['elapsed'], observed_world_seconds=samples[-1]['world_seconds'],
        final_population=samples[-1]['authority_agents'], regions=regions, max_ledger_errors=errors,
        actual_intake_samples=sum(a.get('last_intake', 0) > 0 for s in samples for a in s['agents']),
        active_journey_samples=sum(a.get('migration_active', False) for s in samples for a in s['agents']),
        region_transfers=data['region_transfers'], screenshots=data['screenshots'])


automation = read(raw / 'Automation02/index.json')
assert automation['failed'] == 0 and automation['notRun'] == 0
reload = read(raw / 'AssetReload.json')
assert reload['passed'] and len(reload['weather']) == 3 and len(reload['habitats']) == 9
assert not reload['legacy_visual_weather']
weather_fix=read(raw / 'WeatherCopyFix.json')
assert not weather_fix['remaining']
build = root / 'Saved/IntegrationBuilds/Milestone_Final_20261023_151545.log'
assert 'Result: Succeeded' in build.read_text(encoding='utf-8', errors='replace')
controls=read(raw / 'WeatherControls.json')
assert controls['passed'] and not controls['error']
processes = read(raw / 'NetworkProcesses.json')
assert len(processes) == 3 and all(p['ExitCode'] == 0 for p in processes)
server_log = (raw / 'Server.log').read_text(encoding='utf-8', errors='replace')
assert 'Accessed None' not in server_log and 'NULL AttachComponent' not in server_log
server_summary=summarize_runtime('Server')
transfer_ids={r['id'] for r in server_summary['region_transfers'] if r['destination']=='Forest'}
completed_plans = [dict(plan=int(p), herd=int(h), origin=o, destination=d,
    arrived=int(a), members=int(m)) for p, h, o, d, a, m in re.findall(
    r'\[HerdMigration\] Plan=(\d+) Herd=(\d+) State=Settled Reason=JourneyComplete From=(\w+) To=(\w+) Arrived=(\d+)/(\d+)', server_log)]
clients = []
for name in ('ClientA', 'ClientB'):
    client = read(raw / (name + '_Client.json'))
    log = (raw / (name + '.log')).read_text(encoding='utf-8', errors='replace')
    zero_step = bool(re.search(r'NetMode=3 LogicalOwned=0 .* Step=0', log))
    received_rain_fx = bool(re.search(r'날씨 연출 \| .* → 비 ', log))
    assert client['passed'] and client['authority_agents'] == 0 and zero_step
    assert client['local_migration_subsystems']==0
    assert len(client['best']['fields']) == 3
    assert all(f['visual_material'].startswith('/Game/JYU/Ecosystem/MI_JYU_EcosystemGrass.')
               for f in client['best']['fields'])
    clients.append(dict(name=name, passed=True, authority_agents=0, zero_native_step=zero_step,
        local_migration_subsystems=client['local_migration_subsystems'],
        received_migrated_forest_ids=sorted({v['id'] for s in client['samples'] for v in s['visuals']
            if v['region']=='Forest' and v['id'] in transfer_ids}),
        received_rain_fx=received_rain_fx, fields=client['best']['fields']))

report = dict(date='2026-10-23', baseline_head='ecfd82fab04d16531ae7e00a2adaf3a4737d2fcf',
    branch='codex/social-shelter-handoff', dirty=True,
    policy_weights_changed=False, python_retraining=False,
    map='/Game/JYU/Maps/LV_JYU_Ecosystem', assets=read(root / 'Saved/Vegetation_20261023/BPAuthoring.json'),
    saved_asset_reload=dict(passed=True, weather_actors=3, habitat_actors=9, blueprints=6),
    weather_copy_cleanup=weather_fix,
    build=dict(succeeded=True, log=str(build.relative_to(root))),
    full_network_and_pie_build='Saved/IntegrationBuilds/Milestone_B_20261023_145312.log',
    final_build_change='Received weather now honors local visuals OFF and density controls; no simulation/DTO change. Final automation and actual PIE controls tested after rebuilding.',
    final_weather_controls=controls,
    automation={k: automation[k] for k in ('succeeded', 'succeededWithWarnings', 'failed', 'notRun', 'totalDuration')},
    pie=summarize_runtime('PIE02'), server=server_summary, clients=clients,
    server_full_270_second_log=dict(completed_plans=completed_plans,
        completion_may_include_dead_members=True,
        note='Detailed sampler stops at 210 seconds; these normal server lifecycle log events continue until exit'),
    process_exits=[dict(name=p['Name'], exit_code=p['ExitCode']) for p in processes],
    limitations=[
        'Authored periodic climate, not stochastic seasonal weather or ecological equilibrium',
        'Representative exact cell visuals <=256 per region; all three plant types currently share the grass mesh',
        'Riparian BP is an unplaced template; no verified connected water surface in the three native stages',
        'No complete ecosystem save, conditional natural birth/genome/body pipeline, experience system or trace investigation',
        'No Python soil-world parity/retraining, cook/package or server/client p95 and bandwidth claim',
        'A short observer session does not prove long-term survival, migration settlement or balance'])
dest.mkdir(parents=True, exist_ok=True)
(dest / 'EcosystemBP_20261023.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
for i in (0, 2):
    shutil.copyfile(raw / ('VegetationPIE_' + str(i) + '.png'), dest / ('EcosystemBP_PIE_' + str(i) + '_20261023.png'))
print(json.dumps(dict(automation=report['automation'], pie=report['pie']['max_ledger_errors'],
    server=report['server']['max_ledger_errors'], clients=[dict(name=c['name'], passed=c['passed'],
    rain_fx=c['received_rain_fx']) for c in clients]), ensure_ascii=False, indent=2))

"""Condense completed engine observations; never generates simulation results."""
import json,re
from pathlib import Path

root=Path(__file__).resolve().parents[2]
source=root/'Saved/HerdMigration_20261022'
target=root/'Docs/조연우/Evidence/JYU_V3/HerdMigration_20261023.json'
def read(name):return json.loads((source/name).read_text(encoding='utf-8-sig'))
def condense(name):
    data=read(name+'_Runtime.json');summary=data['summary']
    assert summary['result']=='FINISHED' and summary['food_loss_fixture'] and not summary['error'],summary
    by_id={};plan_states=set();reasons=set();example=None;max_history=0
    for sample in data['samples']:
        for row in sample['agents']:
            by_id.setdefault(row['stable_id'],[]).append(row)
            if row.get('migration_plan',0)>0:plan_states.add(row.get('migration_state',''))
            reasons.add(row.get('decision_reason',''))
            history=row.get('reason_history',[]);max_history=max(max_history,len(history))
            if row.get('migration_reason')=='Arrived' and len(history)>3:example=row
    transfers=summary['region_transfers']
    identity=[]
    for item in transfers:
        rows=[r for r in by_id[str(item['id'])] if r.get('migration_plan',0)>0]
        identity.append({'id':str(item['id']),'plan_ids':sorted({r['migration_plan'] for r in rows}),
            'herd_ids':sorted({r.get('herd_id','') for r in rows if r.get('migration_active') or r.get('migration_reason')=='Arrived'})})
    assert max_history<=16
    assert all(len(r['plan_ids'])==1 for r in identity)
    return {'summary':summary,'observed_plan_states':sorted(plan_states),'observed_primary_reasons':sorted(reasons),
        'maximum_history_size':max_history,'transferred_identity':identity,
        'maximum_sampled_region_crossing_distance_cm':max((r['distance_cm'] or 0 for r in transfers),default=0),
        'arrival_example':{k:example[k] for k in ('stable_id','herd_id','region','migration_plan','migration_state','migration_reason','native_world_position','reason_history') if k in example} if example else None}

automation=read('Automation07/index.json')
assert automation['failed']==automation['notRun']==0
assert 'Result: Succeeded' in (source/'Build13.log').read_text(encoding='utf-8-sig')
clients=[]
for name in ('ClientA','ClientB'):
    d=read(name+'_Client.json');assert d['passed'] and d['authority_agents']==0 and d['local_migration_subsystems']==0
    clients.append({k:d[k] for k in ('client','passed','authority_agents','local_migration_subsystems','refuges','ready','visible')}|
        {'maximum_visuals':len(d['visuals']),'observations':len(d['observations']),
         'received_id_regions':sorted({(r['id'],r['region']) for s in d['observations'] for r in s['visuals']})})
server=condense('Server');pie=condense('PIE')
assert server['summary']['region_transfers'] and pie['summary']['region_transfers']
transferred={str(r['id']) for r in server['summary']['region_transfers']}
for c in clients:c['received_migrated_agents_in_forest']=sorted({i for i,r in c['received_id_regions'] if i in transferred and r=='Forest'})
processes=read('NetworkProcesses.json');assert all(p['ExitCode']==0 for p in processes)
for name in ('NetworkServer','PIE'):
    log=(source/(name+'.log')).read_text(encoding='utf-8-sig')
    assert not re.search(r'Runtime stopped|receipt rejected|Fatal error:|Assertion failed:',log),name
for name in ('HerdPIE_0.png','HerdPIE_1.png','HerdPIE_2.png','HerdPIE_Refuge.png'):assert (source/name).is_file(),name
result={'date':'2026-10-23','base_commit':'3cc772e','map':'/Game/JYU/Maps/LV_JYU_HerdMigration',
    'mode':'Native v3, SocialControl=0, authored herd journeys, 48 deer per region, 3 regions',
    'fixture':'Explicit receipted sustained Barren drought; observer threats disabled. No creature teleport or weight changes.',
    'build':'Direct UnrealBuildTool.exe Build13 succeeded',
    'automation':{k:automation[k] for k in ('succeeded','succeededWithWarnings','failed','notRun')},
    'native_evaluator':'EcoV3Eval rebuilt from the changed engine-free headers (EvaluatorBuild02.log)',
    'network_processes':processes,'clients':clients,'server':server,'pie':pie,
    'limitations':['Controlled drought fixture, not a long-duration natural equilibrium study.',
        'Server raw summary world_elapsed_seconds denotes wall observation duration; individual world_seconds/native_step fields are authoritative.',
        'Uncooked -game logs retain editor AnimGraph/HLOD package import warnings; client meshes and refuges were received. Shipping/cook not verified.',
        'Only Barren-Forest corridor authored; Highland has no validated route. No new Python parity/retraining claim.']}
target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('HERD_EVIDENCE_WRITTEN',target)
print('Server transfers',len(server['summary']['region_transfers']),'PIE transfers',len(pie['summary']['region_transfers']))
print('Client migrated IDs',[(c['client'],c['received_migrated_agents_in_forest']) for c in clients])

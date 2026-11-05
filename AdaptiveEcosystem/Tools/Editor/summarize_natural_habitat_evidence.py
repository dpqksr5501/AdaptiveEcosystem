"""Reduce actual reports to durable, bounded evidence; missing checks stay missing."""
import json,collections
from pathlib import Path
root=Path(__file__).resolve().parents[2]
saved=root/'Saved/NaturalHabitatRelease_20261030'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def food_error(rows):
    return max((abs(f[a]-f[b]) for s in rows for f in s['fields'] for a,b in
        (('food','ledger_amount'),('capacity','ledger_capacity'),('consumed','ledger_consumed'),('grown','ledger_grown'),('environment_lost','ledger_environment_lost'))),default=0)
def experiment(name):
    d=read(saved/(name+'_Life.json'));rows=d['samples'];latest={};previous={};transfers=0;caught={};reasons=collections.Counter()
    for s in rows:
        for a in s['agents']:
            key=a['stable_id'];latest[key]=a
            if key in previous:transfers+=previous[key]['region']!=a['region']
            previous[key]=a
            caught[a['region']]=max(caught.get(a['region'],0),a.get('caught_in_cover',0))
            if a.get('migration_reason'):reasons[a['migration_reason']]+=1
    first_barren={a['stable_id'] for a in rows[0]['agents'] if a['region']=='Barren'}
    end={a['stable_id']:a for a in rows[-1]['agents'] if a.get('hp',0)>0}
    return dict(result=d['result'],seed=d.get('seed'),fixture=d.get('fixture'),requested_simulation_seconds=d.get('fixed_step_simulation_target'),
        last_simulation_seconds=rows[-1].get('simulation_elapsed'),alive_last_sample=len(end),observed_children=len(d['natural_child_ids']),
        observed_transfers=transfers,interior_rest_steps=sum(a.get('life',{}).get('habitat_interior_rest_steps',0) for a in latest.values()),
        edge_rest_steps=sum(a.get('life',{}).get('habitat_edge_rest_steps',0) for a in latest.values()),
        caught_in_cover_by_context=caught,migration_reason_samples=dict(reasons),food_ledger_max_error=food_error(rows),
        original_barren_survivors=sum(k in end for k in first_barren),original_barren_count=len(first_barren),
        final_fields=[{k:f[k] for k in ('region','natural_profile','ground_cells','ground_sites','food','capacity','grown','consumed','environment_lost')} for f in rows[-1]['fields']],
        last_performance=rows[-1].get('performance'))

report=dict(schema=1,date='2026-10-30',scope='Owned LV_JYU_Ecosystem + explicit small transfer fixture; Native v3 opt-in natural profiles',
    raw_folder=str(saved.relative_to(root)),experiments={},limitations=[
    'Not the future designer integration map; no production streaming/cook/package acceptance',
    'Ground-following 2.5D; no overlapping-floor ownership, swimming, river hydraulics or groundwater solver',
    'No new PPO weights, full Python world mirror, permanent equilibrium or all-seed zero-starvation proof',
    'Three plant guilds and reused Doe rig proportions; no complete biome species library or bespoke fawn model',
    'Recent browse marks are bounded transient presentation evidence, not persisted plant individuals or a second food balance'])
for name in ('Natural23','Natural47','Drought23','NoPredators47'):
    p=saved/(name+'_Life.json')
    report['experiments'][name]=experiment(name) if p.exists() else {'result':'MISSING'}
p=saved/'AutomationFinal/index.json'
if p.exists():
    a=read(p);report['automation']={k:a[k] for k in ('succeeded','succeededWithWarnings','failed','notRun')}
p=saved/'NaturalPIE_Runtime.json'
if p.exists():
    d=read(p);reps=[r for s in d['samples'] for r in s.get('representations',[])]
    report['play']=dict(result=d['result'],duration_wall_seconds=d['duration_wall_seconds'],samples=len(d['samples']),
        appearances=sorted({r['appearance'] for r in reps}),child_sightings=sum(r['appearance']==3 for r in reps),
        eating_sightings=sum(bool(r['eating']) for r in reps),screenshots=d['screenshots'])
for name in ('Save','Load'):
    p=saved/(name+'_Life.json')
    if p.exists():
        d=read(p);report[name.lower()]=dict(result=d['result'],operation=d['operation'],food_ledger_max_error=food_error(d['samples']))
p=saved/'TransferFixture.json'
if p.exists():
    d=read(p);report['transfer_fixture']=dict(result=d['result'],error=d.get('error'),map=d['map'],unreachable_height_rejected=d.get('unreachable_height_rejected'),
        last_fields=[{k:f.get(k) for k in ('region','natural_profile','ground_cells','ground_sites','food')} for f in (d.get('samples') or [{}])[-1].get('fields',[])])
network=root/'Saved/NaturalHabitatRelease_20261030_Network'
report['network']={}
for name in ('ClientA','ClientB'):
    p=network/(name+'_Client.json')
    if p.exists():
        d=read(p);report['network'][name]={k:d.get(k) for k in ('passed','authority_agents','local_migration_subsystems','native_performance','morph_matches_payload','scale_payload_matches_actor')}
p=network/'Relevance.json'
if p.exists():report['network']['relevance']=read(p)
builds=list((root/'Saved/IntegrationBuilds').glob('Milestone_Final_*.log'))
if builds:report['latest_build_log']=str(max(builds,key=lambda p:p.stat().st_mtime).relative_to(root))
destination=root/'Docs/Architecture/Evidence/NaturalHabitat_20261030.json'
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(evidence=str(destination),automation=report.get('automation'),experiments={k:{x:v.get(x) for x in ('result','alive_last_sample','interior_rest_steps','edge_rest_steps','food_ledger_max_error')} for k,v in report['experiments'].items()}),ensure_ascii=False))

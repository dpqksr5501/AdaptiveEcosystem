"""Independent checks of observed food/pose/ledger/transport, beyond observer exit."""
import json,math
from pathlib import Path
root=Path(__file__).resolve().parents[2]
folder=root/'Saved/NaturalHabitatRecheck_20261030'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
play=read(folder/'NaturalPIE_Runtime.json')
checks={'observer_finished':play['result']=='FINISHED'}
feeding=[];morph=[];bad_cells=[];error=0.;latest={};grown={};consumed={};events={}
matches=0
for sample in play['samples']:
    agents={a['stable_id']:a for a in sample['agents']};latest.update(agents)
    for r in sample['representations']:
        a=agents.get(r['id'])
        if not a:continue
        if a['species']=='Herbivore':
            matches+=1
            if r['eating']!=(a.get('last_plant_intake',0)>1e-9):feeding.append([sample['elapsed'],r['id']])
            expected='SK_DeerStag' if r['appearance']==1 else 'SK_DeerDoe' if r['appearance'] in (2,3) else None
            if expected and (not r['mesh'] or expected not in r['mesh'] or not r['animation']):morph.append([sample['elapsed'],r['id']])
        elif r['appearance']!=0:morph.append([sample['elapsed'],r['id'],'wolf_using_deer_variant'])
    for f in sample['fields']:
        region=f['region'];grown[region]=max(grown.get(region,0),f['grown']);consumed[region]=max(consumed.get(region,0),f['consumed'])
        events[region]=max(events.get(region,0),f['browse_intake_events'])
        for a,b in (('food','ledger_amount'),('capacity','ledger_capacity'),('grown','ledger_grown'),('consumed','ledger_consumed'),('environment_lost','ledger_environment_lost')):
            error=max(error,abs(f[a]-f[b]))
        for c in f['logical_cells']:
            if not all(math.isfinite(c[k]) for k in ('food','capacity','moisture','stress')) or not (-1e-9<=c['food']<=c['capacity']+1e-9 and 0<=c['moisture']<=1 and 0<=c['stress']<=1):bad_cells.append([region,c['cell']])
edge=sum(a.get('life',{}).get('habitat_edge_rest_steps',0) for a in latest.values())
dark_intervals=0;dark_growth=[]
for before,after in zip(play['samples'],play['samples'][1:]):
    old={f['region']:f for f in before['fields']}
    for f in after['fields']:
        p=old.get(f['region'])
        if p and p['light']==f['light']==0 and after['elapsed']-before['elapsed']<15:
            dark_intervals+=1
            if abs(f['grown']-p['grown'])>1e-8:dark_growth.append([f['region'],before['elapsed'],after['elapsed']])
checks.update(positive_observed_intake=all(v>0 for v in consumed.values()),positive_observed_growth=all(v>0 for v in grown.values()),
    feeding_matches_actual_intake=matches>0 and not feeding,morph_matches_species=not morph,valid_logical_cells=not bad_cells,
    ledger_matches=error<1e-8,no_observed_edge_rest=edge==0,observed_interior_rest=any(a.get('life',{}).get('habitat_interior_rest_steps',0)>0 for a in latest.values()),
    no_growth_in_observed_dark_intervals=dark_intervals>0 and not dark_growth)
network=root/'Saved/NaturalHabitatRecheck_20261030_Network'
relevance=read(network/'Relevance.json');checks['network_relevance']=relevance['passed']
clients={}
for name in ('ClientA','ClientB'):
    d=read(network/(name+'_Client.json'))
    clients[name]={k:d.get(k) for k in ('passed','authority_agents','morph_matches_payload','scale_payload_matches_actor')}
    checks[name]=d['passed'] and d['authority_agents']==0 and d['native_performance']['native_steps_total']==0
report=dict(scope='Fresh 165-second PIE and dedicated+two clients; same runtime as prior release, before read-only authoring-report fix',
    passed=all(checks.values()),checks=checks,matched_herbivore_visual_samples=matches,feeding_mismatches=feeding,morph_mismatches=morph,
    bad_cells=bad_cells[:20],max_ledger_error=error,grown=grown,consumed=consumed,browse_events=events,
    observed_dark_region_intervals=dark_intervals,dark_growth_violations=dark_growth,
    interior_rest_steps=sum(a.get('life',{}).get('habitat_interior_rest_steps',0) for a in latest.values()),edge_rest_steps=edge,
    clients=clients,relevance=relevance,
    remaining=['Existing Landscape physical-material-task warnings','Drought starvation and long-term equilibrium remain unresolved','Future production integration map/streaming/cook not tested','2.5D backend; overlapping floors/swimming unsupported'])
path=root/'Docs/Architecture/Evidence/NaturalHabitatRecheck_20261030.json'
transfer_path=folder/'TransferFixture.json'
if transfer_path.exists():
    d=read(transfer_path)
    report['authoring_fix_regression']={k:d.get(k) for k in ('result','custom_wading_limit_detected','unreachable_height_rejected')}
    report['checks']['authoring_fix_regression']=d['result']=='FINISHED' and d.get('custom_wading_limit_detected') is True
automation_path=folder/'AutomationFinal/index.json'
if automation_path.exists():
    d=read(automation_path);report['automation']={k:d[k] for k in ('succeeded','succeededWithWarnings','failed','notRun')}
    report['checks']['automation']=d['failed']==d['notRun']==0
report['passed']=all(report['checks'].values())
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
if not report['passed']:raise SystemExit(1)

"""Check near-field delivery through actual client camera transitions, not peak counts."""
import json,sys
from pathlib import Path

folder=Path(sys.argv[1]).resolve()
def read(name):return json.loads((folder/name).read_text(encoding='utf-8-sig'))
server=read('Server_Runtime.json')
if server['result']!='FINISHED':raise RuntimeError('Completed authority observer required')
origins={f['region']:(f['actor_location'],f['net_cull_distance_squared']) for f in server['samples'][0]['fields']}
if len(origins)!=3:raise RuntimeError('Three authority field origins required')
result=dict(grace_seconds=3,clients=[],passed=True)
for name in ('ClientA','ClientB'):
    client=read(name+'_Client.json');since={};missing=[];checked=0;evaluated=set();received=set();missing_camera=[]
    for sample in client['samples']:
        camera=sample['observer_camera'];present={f['region'] for f in sample['fields']};received.update(present)
        if camera is None:
            if sample['elapsed']>3:missing_camera.append(sample['elapsed'])
            continue
        for region,(point,radius_sq) in origins.items():
            if sum((a-b)**2 for a,b in zip(camera,point))>=radius_sq:
                since.pop(region,None);continue
            since.setdefault(region,sample['elapsed'])
            if sample['elapsed']-since[region]<=3:continue
            checked+=1;evaluated.add(region)
            if region not in present:missing.append(dict(elapsed=sample['elapsed'],region=region,camera=camera))
    passed=client['passed'] and client['authority_agents']==client['local_migration_subsystems']==0 and not missing and not missing_camera and len(evaluated)>=2
    result['clients'].append(dict(name=name,passed=passed,checked_near_region_samples=checked,
        evaluated_regions=sorted(evaluated),received_regions=sorted(received),missing_after_grace=missing,missing_camera_samples=missing_camera))
    result['passed']&=passed
result['passed']&=set(origins)=={r for c in result['clients'] for r in c['received_regions']}
if server.get('overlap_expected'):
    concurrent=[s['elapsed'] for s in server['samples'] if s.get('players',0)>=2]
    span=max(concurrent)-min(concurrent) if concurrent else 0
    result['concurrent_clients']=dict(samples=len(concurrent),observed_span_seconds=span,passed=len(concurrent)>=3 and span>=15)
    result['passed']&=result['concurrent_clients']['passed']
children={}
for sample in server['samples']:
    for a in sample.get('agents',[]):
        if a.get('life',{}).get('origin')==1 and a.get('hp',0)>0:
            children.setdefault(a['stable_id'],[]).append(a['body_scale'])
if any(a.get('ecosystem_life_enabled') for s in server['samples'] for a in s.get('agents',[])):
    late=read('ClientB_Client.json')
    received=[v for s in late['samples'] for v in s['visuals'] if v['id'] in children]
    mismatched=[v for v in received if not min(children[v['id']])-2/128<=v['body_scale']<=max(children[v['id']])+2/128]
    result['late_join_life']=dict(authority_child_ids=sorted(children),received_child_ids=sorted({v['id'] for v in received}),
        scale_tolerance=2/128,scale_mismatches=mismatched,passed=bool(received) and not mismatched)
    result['passed']&=result['late_join_life']['passed']
(folder/'Relevance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
if not result['passed']:raise SystemExit(1)

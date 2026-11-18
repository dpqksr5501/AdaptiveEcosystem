"""Check near-field delivery through actual client camera transitions, not peak counts."""
import json,sys
from pathlib import Path

folder=Path(sys.argv[1]).resolve()
food_patch_check='--food-patch' in sys.argv[2:]
def read(name):return json.loads((folder/name).read_text(encoding='utf-8-sig'))
server=read('Server_Runtime.json')
if server['result']!='FINISHED':raise RuntimeError('Completed authority observer required')
origins={f['region']:(f['actor_location'],f['net_cull_distance_squared']) for f in server['samples'][0]['fields']}
island = server.get('map') == 'LV_JYU_IslandEcosystemRefreshed'
expected_fields = 4 if island or any(r.startswith('JWJ_') for r in origins) else 3
if len(origins)!=expected_fields:raise RuntimeError(f'{expected_fields} authority field origins required')
result=dict(grace_seconds=3,clients=[],passed=True,scope='Food patch delivery/anchors only; life/three-region camera circuit not evaluated' if food_patch_check else 'Legacy vegetation/life/camera circuit')
patch_layout=server.get('patch_layout',False)
source_anchors={}
if patch_layout:
    for sample in server['samples']:
        if sample['elapsed']<15:continue
        for f in sample['fields']:
            source_anchors.setdefault(f['region'],set()).add((f['patch_layout_epoch'],f['patch_layout_hash'],
                f['published_patch_anchors'],f['patch_anchor_checksum']))
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
    passed=client['passed'] and client['authority_agents']==client['local_migration_subsystems']==0 and not missing and not missing_camera and len(evaluated)>=(1 if food_patch_check else 2)
    travel=None
    if client.get('grass_travel'):
        visits=[]
        for sample in client['samples']:
            region=sample.get('nearest_region')
            if not region: continue
            if not visits or visits[-1]['region']!=region:
                visits.append(dict(region=region,start=sample['elapsed'],end=sample['elapsed'],settled_render=False))
            visit=visits[-1];visit['end']=sample['elapsed']
            visit['settled_render'] |= bool(sample['streaming_completed']) and any(
                f['region']==region and f['near_instances']>0 for f in sample['fields'])
        stable=[v for v in visits if v['end']-v['start']>=2]
        counts={region:sum(v['region']==region for v in stable) for region in origins}
        travel=dict(stable_visits=stable,visits_per_region=counts,
            ten_stable_visits_per_region=all(n>=10 for n in counts.values()),
            rendered_after_streaming=all(v['settled_render'] for v in stable))
        passed &= travel['ten_stable_visits_per_region'] and travel['rendered_after_streaming']
    result['clients'].append(dict(name=name,passed=passed,checked_near_region_samples=checked,
        evaluated_regions=sorted(evaluated),received_regions=sorted(received),missing_after_grace=missing,missing_camera_samples=missing_camera,grass_travel=travel))
    if island:
        authority_species = {str(a['stable_id']): a['species'] for s in server['samples'] for a in s['agents']}
        received_species = {str(v['id']): v['species'] for s in client['samples'] for v in s['visuals']}
        mismatched = {key: value for key, value in received_species.items()
                      if key in authority_species and authority_species[key] != value}
        matched = {kind for key, kind in received_species.items() if authority_species.get(key) == kind}
        island_pass = len(set(authority_species.values())) == 16 and len(matched) >= 2 and not mismatched
        result['clients'][-1]['island_species'] = dict(matched=sorted(matched), mismatched=mismatched, passed=island_pass)
        passed &= island_pass
        result['clients'][-1]['passed'] = passed
    if patch_layout:
        matched=set();anchor_errors=[]
        for sample in client['samples']:
            if sample['elapsed']<=3:continue
            for f in sample['fields']:
                signature=(f['patch_layout_epoch'],f['patch_layout_hash'],f['published_patch_anchors'],f['patch_anchor_checksum'])
                if f['patch_layout_mode']==1 and signature in source_anchors.get(f['region'],set()):matched.add(f['region'])
                if f['rendered_authority_anchor_error_cm']>2:anchor_errors.append((sample['elapsed'],f['region']))
        anchor_pass=matched==set(origins) and not anchor_errors
        result['clients'][-1]['patch_anchors']=dict(matching_regions=sorted(matched),anchor_errors=anchor_errors,passed=anchor_pass)
        passed &= anchor_pass
        result['clients'][-1]['passed']=passed
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
        rule = a.get('rule_fauna', {})
        born = a.get('life',{}).get('origin')==1 or island and int(rule.get('parent_a', '0')) > 0 and int(rule.get('parent_b', '0')) > 0
        if born and a.get('hp',0)>0:
            children.setdefault(a['stable_id'],[]).append(a['body_scale'])
if not food_patch_check and any(a.get('ecosystem_life_enabled') for s in server['samples'] for a in s.get('agents',[])):
    late=read('ClientB_Client.json')
    received=[v for s in late['samples'] for v in s['visuals'] if v['id'] in children]
    mismatched=[v for v in received if not min(children[v['id']])-2/128<=v['body_scale']<=max(children[v['id']])+2/128]
    result['late_join_life']=dict(authority_child_ids=sorted(children),received_child_ids=sorted({v['id'] for v in received}),
        scale_tolerance=2/128,scale_mismatches=mismatched,passed=bool(received) and not mismatched)
    result['passed']&=result['late_join_life']['passed']
(folder/'Relevance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
if not result['passed']:raise SystemExit(1)

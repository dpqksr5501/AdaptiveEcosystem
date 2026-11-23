"""Check near-field delivery through actual client camera transitions, not peak counts."""
from collections import defaultdict
import json,sys
from pathlib import Path

folder=Path(sys.argv[1]).resolve()
food_patch_check='--food-patch' in sys.argv[2:]
fauna_experience='--fauna-experience' in sys.argv[2:]
all_island_social='--all-island-social' in sys.argv[2:]
late_join_social='--late-join-social' in sys.argv[2:]
fauna_interactions='--fauna-interactions' in sys.argv[2:]
watch_fauna_alarms='--watch-fauna-alarms' in sys.argv[2:]
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
    passed=client['passed'] and client['authority_agents']==client['local_migration_subsystems']==0
    if not all_island_social:
        passed &= not missing and not missing_camera and len(evaluated)>=(1 if food_patch_check else 2)
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
if not all_island_social:
    result['passed']&=set(origins)=={r for c in result['clients'] for r in c['received_regions']}
if server.get('overlap_expected'):
    concurrent=[s['elapsed'] for s in server['samples'] if s.get('players',0)>=2]
    span=max(concurrent)-min(concurrent) if concurrent else 0
    result['concurrent_clients']=dict(samples=len(concurrent),observed_span_seconds=span,passed=len(concurrent)>=3 and span>=15)
    result['passed']&=result['concurrent_clients']['passed']
if fauna_experience:
    authority_conditions=defaultdict(set)
    authority_exchanges={}
    for sample in server['samples']:
        for agent in sample['agents']:
            authority_conditions[agent['stable_id']].add(agent['body_condition'])
            for event in agent.get('gameplay_reason_history', []):
                if event['reason'] == 'SocialExchangeCompleted':
                    authority_exchanges[(agent['stable_id'],event['related_id'],event['time'])]=agent['species']
    reciprocal={(owner,peer,at): species for (owner,peer,at),species in authority_exchanges.items()
                if authority_exchanges.get((peer,owner,at))==species}
    completed={owner for owner,_,_ in reciprocal}
    reply_times=defaultdict(list)
    for (owner,peer,at),species in reciprocal.items():
        reply_times[owner,species].append((at,peer))
    condition_checks=[]
    social_checks=[]
    for name in ('ClientA','ClientB'):
        visual_conditions=defaultdict(list)
        signals=defaultdict(set)
        received_reply_species=set()
        invalid=[]
        client_report=read(name+'_Client.json')
        for sample in client_report['samples']:
            for visual in sample['visuals']:
                key=(visual['id'],visual['species'],visual['mesh'],visual['appearance'])
                visual_conditions[key].append((visual['body_condition'],visual['mesh_scale']))
                role=visual['social_signal']
                signals[role].add(visual['id'])
                if role==2 and visual['id'] in completed:
                    received_reply_species.add(visual['species'])
                if role not in (0,1,2) or not 0<=visual['social_yaw']<360:
                    invalid.append((visual['id'],role,visual['social_yaw']))
        matched,native_matched,updated,errors=set(),set(),set(),[]
        for (agent,species,asset,_), rows in visual_conditions.items():
            authoritative=authority_conditions.get(agent)
            if not authoritative:
                continue
            native=species in ('Wolf','Herbivore')
            for value,_ in rows:
                if min(abs(value-source) for source in authoritative)>1/128:
                    errors.append(dict(agent=agent, received=value, authoritative=sorted(authoritative)))
                if value != 1 and value in authoritative:
                    (native_matched if native else matched).add(agent)
            # Deer growth also changes mesh scale, so verify its payload above.
            if native or not asset or len({value for value,_ in rows})<2:
                continue
            value,scale=rows[0]
            baseline=(scale[0]/value,scale[1]/value,scale[2])
            if all(all(abs(a-b)<1e-4 for a,b in zip(baseline,(mesh[0]/current,mesh[1]/current,mesh[2])))
                   for current,mesh in rows):
                updated.add(agent)
            else:
                errors.append(dict(agent=agent, reason='mesh proportions did not follow replicated condition'))
        passed=bool(matched) and bool(native_matched) and bool(updated) and not errors
        condition_checks.append(dict(name=name,non_neutral_matches=sorted(matched),native_matches=sorted(native_matched),live_mesh_updates=sorted(updated),
                                     errors=errors,passed=passed))
        if not all_island_social:
            result['passed']&=passed
        # Offers may be cancelled on the next server sample. Require completed replies
        # and observe a transition back to no signal on at least one rendered identity.
        cleared=signals[0] & (signals[1] | signals[2])
        social_pass=bool(signals[1] and signals[2] & completed and cleared) and not invalid
        if late_join_social:
            transitions=client_report.get('social_transitions', [])
            for transition in transitions:
                signals[transition['role']].add(transition['id'])
            for species,rows in client_report.get('social_rendered_replies', {}).items():
                for row in rows:
                    offers={t['id']: t['time'] for t in transitions if t['role']==1
                            and abs(t['time']-row['server_time'])<=2.5}
                    nearby=[(abs(row['server_time']-at),at,peer) for at,peer in reply_times[row['id'],species]
                            if abs(row['server_time']-at)<=2.5 and peer in offers]
                    cleared_at=min((t['time'] for t in transitions if t['id']==row['id'] and t['role']==0
                                    and t['time']>row['server_time']), default=None)
                    if not nearby or cleared_at is None:
                        continue
                    _,at,peer=min(nearby)
                    result.setdefault('late_join_witnesses', {}).setdefault(name, dict(row, authority_time=at,
                        peer_id=peer, offer_received_time=offers[peer], reply_cleared_time=cleared_at))
                    received_reply_species.add(species)
            witness=result.get('late_join_witnesses', {}).get(name)
            if witness:
                cleared.add(witness['id'])
            social_pass=bool(witness) and not invalid and not client_report.get('social_render_error')
        social_checks.append(dict(name=name,offer_ids=sorted(signals[1]),reply_ids=sorted(signals[2] & completed),
                                  cleared_ids=sorted(cleared),reply_species=sorted(received_reply_species),errors=invalid,passed=social_pass))
        if not all_island_social:
            result['passed']&=social_pass
    result['body_condition']=condition_checks
    result['social_experience']=dict(server_species=sorted(set(reciprocal.values())),
                                     server_exchanges=len(reciprocal)//2,clients=social_checks)
    if all_island_social:
        expected={row['species'] for row in server['samples'][0]['agents']}
        visible={}
        raw_visible={}
        for name in ('ClientA','ClientB'):
            report=read(name+'_Client.json')
            if report.get('social_render_error'):
                raise RuntimeError(f"{name} rendered reply audit failed: {report['social_render_error']}")
            observations=report['social_rendered_replies']
            raw_visible[name]=sorted(observations)
            for species,rows in observations.items():
                for row in rows:
                    plausible=[(abs(row['server_time']-at),at,peer) for at,peer in reply_times[row['id'],species]
                               if abs(row['server_time']-at)<=2.5]
                    if plausible:
                        _,event_time,peer=min(plausible)
                        visible.setdefault(species, {})[name]=dict(row, authority_time=event_time, peer_id=peer)
                        break
        missing=expected-set(visible)
        both={client for observations in visible.values() for client in observations}=={'ClientA','ClientB'}
        passed=len(expected)==16 and not missing and both
        result['scope']='Saved island; rendered social reply matched to reciprocal authority event'
        result['all_island_social']=dict(expected=sorted(expected),missing=sorted(missing),raw_client_species=raw_visible,
                                         species_count=len(visible),evidence=visible,passed=passed)
        result['passed']&=passed
if fauna_interactions:
    alarms = {}
    for sample in server['samples']:
        for agent in sample.get('agents', []):
            for event in agent.get('gameplay_reason_history', []):
                if event['reason'] == 'FaunaAlarmEmitted':
                    alarms.setdefault((agent['stable_id'], agent['species']), set()).add(event['time'])
    authority_transitions = defaultdict(set)
    if watch_fauna_alarms:
        for row in server['fauna_alarm_transitions']:
            authority_transitions[row['id'], row['species']].add(row['server_time'])
    observations = {}
    for name in ('ClientA', 'ClientB'):
        report = read(name+'_Client.json')
        received = {(visual['id'], visual['species'], sample['server_time'])
                    for sample in report['samples'] for visual in sample['visuals'] if visual['fauna_alarm']}
        if watch_fauna_alarms:
            received = {(row['id'], row['species'], row['server_time']) for row in report['fauna_alarm_transitions']}
        matched = [(agent, species, at) for agent, species, at in sorted(received)
                   if any(-.5 <= at - published <= 1.5 for published in authority_transitions[agent, species])
                   or any(-.5 <= at - issued <= 4. for issued in alarms.get((agent, species), ()))]
        observations[name] = dict(received=len(received), matched=len(matched), matched_species=sorted({row[1] for row in matched}))
    result['fauna_alarm'] = dict(authority_emissions=sum(len(times) for times in alarms.values()),
        authority_presentation_transitions=sum(len(times) for times in authority_transitions.values()), clients=observations)
    if watch_fauna_alarms:
        result['scope'] = 'Saved island; alarm display received and compared with authority presentation'
        result['fauna_alarm']['passed'] = all(row['matched'] > 0 for row in observations.values())
        result['passed'] &= result['fauna_alarm']['passed']
children={}
for sample in server['samples']:
    for a in sample.get('agents',[]):
        rule = a.get('rule_fauna', {})
        born = a.get('life',{}).get('origin')==1 or island and int(rule.get('parent_a', '0')) > 0 and int(rule.get('parent_b', '0')) > 0
        if born and a.get('hp',0)>0:
            children.setdefault(a['stable_id'],[]).append(a['body_scale'])
if not food_patch_check and not all_island_social and any(a.get('ecosystem_life_enabled') for s in server['samples'] for a in s.get('agents',[])):
    late=read('ClientB_Client.json')
    received=[v for s in late['samples'] for v in s['visuals'] if v['id'] in children]
    mismatched=[v for v in received if not min(children[v['id']])-2/128<=v['body_scale']<=max(children[v['id']])+2/128]
    result['late_join_life']=dict(authority_child_ids=sorted(children),received_child_ids=sorted({v['id'] for v in received}),
        scale_tolerance=2/128,scale_mismatches=mismatched,passed=bool(received) and not mismatched)
    result['passed']&=result['late_join_life']['passed']
(folder/'Relevance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
if not result['passed']:raise SystemExit(1)

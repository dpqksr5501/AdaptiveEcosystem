"""Independent acceptance of observed age/growth/family/food data, no Unreal dependency."""
import json,math,sys,statistics,collections,re
from pathlib import Path
root=Path(__file__).resolve().parents[2]
audit_name=sys.argv[1] if len(sys.argv)>1 else 'NaturalPopulationBoundary_20261030'
if not re.fullmatch(r'[A-Za-z0-9_]+',audit_name):raise ValueError('Simple audit folder required')
folder=root/'Saved'/audit_name
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
r=read(folder/'NaturalPIE_Runtime.json');samples=r['samples'];first=[a for a in samples[0]['agents'] if a['species']=='Herbivore']
ages=[a['life']['age_seconds'] for a in first];young=sum(a['life']['maturity']<1 for a in first)
latest={};dead_maturity={};family_bonds={};regions=collections.defaultdict(set);bad=[];matches=0;ledger=0;stale=[];age_errors=[]
for sample in samples:
    agents={a['stable_id']:a for a in sample['agents']}
    for a in agents.values():
        life=a.get('life',{});regions[a['stable_id']].add(a.get('region'));
        if a['species']=='Herbivore':family_bonds.setdefault(a['stable_id'],set()).add(life.get('caregiver'))
        before=latest.get(a['stable_id']);latest[a['stable_id']]=a
        if a['hp']>0 and life.get('family_mode')==2 and (life['maturity']>=1 or life['age_seconds']+life['born']-life['family_last_seen']>3.1):stale.append(a['stable_id'])
        if before and a['hp']>0 and a['species']=='Herbivore' and before['life']['growth']>life['growth']+1e-9:bad.append(a['stable_id'])
    for v in sample['representations']:
        a=agents.get(v['id'])
        if not a:continue
        matches+=1
        if a['species']=='Herbivore' and abs(v['coat_tone']-(a['life']['coat_gene']-.85)/.3)>1/255:bad.append(['coat',v['id']])
        if a['hp']>0 and abs(v['maturity']-min(1,a['life']['age_seconds']/a['life']['maturity_seconds']))>2/255:age_errors.append(v['id'])
        if a['hp']<=0:
            previous=dead_maturity.setdefault(v['id'],v['maturity'])
            if previous!=v['maturity']:bad.append(['corpse_growing',v['id']])
        if a['species']=='Herbivore':
            expected=1 if a['life']['sex']==2 else 2
            if v['appearance']!=expected:bad.append(v['id'])
            if not(v['adult_visible'] or v['young_visible']):bad.append(v['id'])
            if v['appearance']==1 and v['maturity']<.6 and (v['adult_visible'] or not v['young_visible']):bad.append(['young_antlers',v['id']])
            if v['maturity']>=1 and v['young_visible']:bad.append(['adult_immature_mesh',v['id']])
    for f in sample['fields']:
        for k in ('food','grown','consumed','environment_lost'):ledger=max(ledger,abs(f[k]-f['ledger_amount' if k=='food' else 'ledger_'+k]))
        for c in f.get('logical_cells',[]):
            if not math.isfinite(c['development']) or not 0<=c['development']<=1:bad.append(['plant',f['region'],c['cell']])
checks={'pie_finished':r['result']=='FINISHED','initial_mixed_ages':len(set(ages))>=100 and young==36,
        'initial_sexes':{a['life']['sex'] for a in first}=={1,2},'growth_and_appearance_valid':not bad,
        'age_transport_matches_authority':matches>0 and not age_errors,'family_follow_observed':any(a.get('life',{}).get('family_follow_steps',0)>0 for a in latest.values()),
        'family_has_fresh_local_evidence':not stale,'food_ledger_conserved':ledger<1e-8,'existing_policy_contract':all(a.get('policy_obs_dim')==18 and a.get('policy_mask_version')==2 and a.get('movement')=='NativeV3_single_writer' for sample in samples for a in sample['agents'] if a['species']=='Herbivore'),'family_bonds_preserved':all(len(b)==1 for b in family_bonds.values())}
result={'checks':checks,'passed':all(checks.values()),'initial_deer':len(first),'initial_juveniles':young,
        'founder_age_range':[min(ages),max(ages)],'matched_visuals':matches,'max_ledger_error':ledger,
        'family_following_agents':sum(a.get('life',{}).get('family_follow_steps',0)>0 for a in latest.values()),'bad':bad[:20],'age_errors':age_errors[:20],'stale':stale[:20]}
# Optional real process runs are claimed only when their report exists.
for name in ('Save','Load'):
    p=folder/(name+'_Life.json')
    if p.exists():
        q=read(p);result[name.lower()]={'result':q['result'],'operation':q.get('operation')}
network=root/'Saved'/(audit_name+'_Network')
if (network/'Relevance.json').exists():
    result['network']={'relevance':read(network/'Relevance.json')['passed']}
    for name in ('ClientA','ClientB'):
        q=read(network/(name+'_Client.json'));result['network'][name]={'passed':q['passed'],'authority_agents':q['authority_agents'],'received_juvenile_ids':sorted({v['id'] for s in q['samples'] for v in s['visuals'] if v['maturity']<1}),
            'native_steps':q['native_performance']['native_steps_total']}
    result['checks']['network_same_build_authority']=all(result['network'][n]['passed'] and result['network'][n]['authority_agents']==0 and result['network'][n]['native_steps']==0 and result['network'][n]['received_juvenile_ids'] for n in ('ClientA','ClientB')) and result['network']['relevance']
for n in ('save','load'):
    if n in result:result['checks'][n+'_passed']=result[n]['result']=='FINISHED'
result['passed']=all(result['checks'].values())
genes=('size_gene','speed_gene','caution_gene','sociability_gene','coat_gene')
result['founder_traits']={g:{'min':min(a['life'][g] for a in first),'max':max(a['life'][g] for a in first),'mean':statistics.mean(a['life'][g] for a in first),'stdev':statistics.pstdev(a['life'][g] for a in first)} for g in genes}
result['checks']['individual_traits_vary']=all(v['stdev']>0 for v in result['founder_traits'].values())
births=[a for a in latest.values() if a['species']=='Herbivore' and a.get('life',{}).get('origin')==1]
parents=collections.Counter(x for a in births for x in (a['life']['parent_a'],a['life']['parent_b']) if x!='0')
result['cohort_observation']={'unique_observed_births':len(births),'contributing_parents':dict(parents),'observed_migrants':sum(len(v)>1 for v in regions.values()),
    'analysis_gate':{'minimum_simulation_seconds':1200,'minimum_births':max(32,math.ceil(len(first)*.25)),'minimum_distinct_parents':8,'ready':samples[-1]['world_seconds']>=1200 and len(births)>=max(32,math.ceil(len(first)*.25)) and len(parents)>=8},'changes_genes':False}
boundary=read(root/'Saved/NaturalPopulationPolicyBoundary_20261030.json')
automation_path=folder/'AutomationFinal/index.json'
if automation_path.exists():
    a=read(automation_path);result['automation']={k:a.get(k) for k in ('succeeded','succeededWithWarnings','failed','notRun')}
    result['checks']['automation_passed']=a['failed']==0 and a['notRun']==0
transfer_path=root/'Saved/NaturalPopulationBoundaryTransfer_20261030/TransferFixture.json'
if transfer_path.exists():
    t=read(transfer_path);result['transfer']={'result':t['result'],'samples':len(t['samples']),'ground_probes':t['authoring']['probes'],'missing_ground':t['authoring']['unavailable_or_ambiguous_ground'],'custom_wading_limit_detected':t['custom_wading_limit_detected'],'unreachable_height_rejected':t['unreachable_height_rejected']}
    result['checks']['separate_level_passed']=t['result']=='FINISHED' and t['authoring']['unavailable_or_ambiguous_ground']==0 and t['custom_wading_limit_detected'] and t['unreachable_height_rejected']
if 'load' in result:result['checks']['cell_development_restored']=result['load']['operation'].get('restored_cell_development_exactly',False)
result['checks']['caution_has_no_policy_consumer']='Genome.Caution' not in (root/'Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp').read_text(encoding='utf-8')
result['checks']['policy_weights_and_inference_unchanged']=all(v['same_as_HEAD_normalized_text'] for v in boundary.values())
result['policy_boundary']=boundary
result['passed']=all(result['checks'].values())
p=root/'Docs/Architecture/Evidence/NaturalPopulation_20261030.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':result['passed'],'checks':result['checks'],'initial_deer':len(first),'initial_juveniles':young,'matched_visuals':matches,'max_ledger_error':ledger,'automation':result.get('automation')},ensure_ascii=False,indent=2))
if not result['passed']:raise SystemExit(1)

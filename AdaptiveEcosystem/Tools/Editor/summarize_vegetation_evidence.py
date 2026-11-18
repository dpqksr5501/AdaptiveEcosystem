"""Summarize fresh UE/native reports without treating unevaluated gates as passes."""
import csv, json, math, re, struct, sys
from collections import deque
from pathlib import Path
root = Path(__file__).resolve().parents[2]

def summarize_grass_network(folder):
    """Read UE5.8 NetworkProfiler.cpp v14; socket bytes and property bits are separate layers."""
    if not re.fullmatch(r'[A-Za-z0-9_]+',folder): raise ValueError('Simple Saved folder required')
    run=root/'Saved'/folder
    processes=json.loads((run/'NetworkProcesses.json').read_text(encoding='utf-8-sig'))
    progress=json.loads((run/'Server_Progress.json').read_text(encoding='utf-8-sig'))
    field_class_names={f['visual_class'].rsplit('.',1)[-1] for f in progress['fields']}
    if not field_class_names:raise ValueError('Actual Field classes required from authority diagnostics')
    pid=next(p['ProcessId'] for p in processes if p['Name']=='Server')
    paths=list((root/'Saved/Profiling').glob('AdaptiveEcosystem-Pid'+str(pid)+'-*.nprof'))
    if len(paths)!=1: raise ValueError('One fresh server profile required: '+str(paths))
    data=paths[0].read_bytes();offset=0
    def read(fmt):
        nonlocal offset
        size=struct.calcsize('<'+fmt)
        if offset+size>len(data): raise ValueError('Truncated network profile at '+str(offset))
        value=struct.unpack_from('<'+fmt,data,offset);offset+=size
        return value[0] if len(value)==1 else value
    def packed():
        value=0
        for shift in range(0,35,7):
            byte=read('B');value|=(byte>>1)<<shift
            if not byte&1:return value
        raise ValueError('Invalid UE SerializeIntPacked')
    def string():
        count=read('i')
        if not 0<=count<=1048576:raise ValueError('Invalid ANSI string length')
        return bytes(read('B') for _ in range(count)).rstrip(b'\0').decode('latin-1')
    def bitarray():
        count=packed()
        for _ in range((count+31)//32):packed()
    magic,version=read('II')
    if (magic,version)!=(0x1DBF348C,14):raise ValueError('Only installed UE5.8 nprof v14 is supported')
    tag,game,url=string(),string(),string()
    names=[];addresses=[];connections={};pending={};tokens={};now=0;frames=[];classes={};eos=False
    def connection():
        return connections.setdefault(current,dict(socket_bytes=0,packets=0,sends=[],properties={},field_actor_calls=0,visual_updates=[],ground_updates=[]))
    current=None
    while offset<len(data):
        token=read('B');tokens[token]=tokens.get(token,0)+1
        if token==0:
            now=read('f');frames.append(now)
        elif token==1:
            packed();size,packet,bunch,ack,padding=read('HHHHH')
            row=connection();row['socket_bytes']+=size;row['packets']+=1;row['sends'].append((now,size))
        elif token==2:read('H');packed();read('HH')
        elif token==3:
            for _ in range(5):packed()
        elif token==4:
            flags=read('B');actor=names[packed()];read('f');classes[actor]=classes.get(actor,0)+1
            properties=pending.pop(current,[])
            if actor in field_class_names:
                row=connection();row['field_actor_calls']+=1
                for name,bits in properties:
                    row['properties'][name]=row['properties'].get(name,0)+bits
                    if name=='VisualGrid':row['visual_updates'].append(dict(time=now,bits=bits,initial=bool(flags&2)))
                    if name=='PatchGround':row['ground_updates'].append(dict(time=now,bits=bits,initial=bool(flags&2)))
        elif token==5:
            name=names[packed()];bits=read('H')
            # Only this custom-delta property has an explicit Connection in UE's
            # TrackReplicateProperty call. Shared plain-property tokens may not.
            if name in ('VisualGrid','PatchGround'):pending.setdefault(current,[]).append((name,bits))
        elif token==6:eos=True;break
        elif token==7:packed();packed()
        elif token==8:
            count=read('H')
            for _ in range(count):read('B')
        elif token in (9,11,15):read('H')
        elif token in (10,13,14):packed();read('H')
        elif token==12:read('HH')
        elif token==16:current=packed()
        elif token==17:names.append(string())
        elif token==18:addresses.append(string())
        elif token==19:
            packed();read('f');bitarray();bitarray();count=packed()
            for _ in range(count):packed()
        elif token==20:packed();read('B');bitarray()
        else:raise ValueError('Unknown nprof token '+str(token)+' at '+str(offset-1))
    if not eos or offset!=len(data):raise ValueError('Missing end marker or trailing profile bytes')
    if len(frames)<2 or frames[-1]<=frames[0]:raise ValueError('Missing capture duration')
    report_connections=[]
    for index,row in connections.items():
        if not row['sends']:continue
        first,last=row['sends'][0][0],row['sends'][-1][0]
        updates=row['visual_updates'];initial=[v for v in updates if v['initial']];delta=[v for v in updates if not v['initial']]
        bins={}
        for time,size in row['sends']:
            second=int(time-first);bins[second]=bins.get(second,0)+size
        report_connections.append(dict(address=addresses[index] if index is not None else 'unattributed',
            socket_sent_bytes=row['socket_bytes'],packets=row['packets'],active_seconds=last-first,
            mean_socket_bytes_per_second=row['socket_bytes']/max(.001,last-first),peak_one_second_socket_bytes=max(bins.values()),
            field_actor_calls=row['field_actor_calls'],raw_profiler_field_property_bits=row['properties'],
            visual_grid_initial=dict(events=len(initial),raw_u16_bits=sum(v['bits'] for v in initial),max_raw_u16_bits=max((v['bits'] for v in initial),default=0)),
            visual_grid_delta=dict(events=len(delta),raw_u16_bits=sum(v['bits'] for v in delta),max_raw_u16_bits=max((v['bits'] for v in delta),default=0))))
    measured=[c for c in report_connections if c['field_actor_calls']]
    audit={}
    text=(run/'Server.log').read_text(encoding='utf-8-sig',errors='replace')
    # The timed observer can stop nprof while a client remains connected. Writer diagnostics after
    # the explicit stop event are outside the profile, and must not be matched against its counters.
    text=text.split('CSVEvent "Cmd: netprofile disable"',1)[0]
    for match in re.finditer(r'\[EcoGrassNet\] Conn=(\S+) Region=(\S+) Bits=(\d+) BaseDynamicBytes=(\d+)',text):
        address,region,bits,base=match.groups();bits=int(bits);base=int(base)
        # UE5.8 FRepLayout::SendCustomDeltaProperty writes one FastArray support bit
        # before our single (ArrayDim=1) struct callback. The profiler includes it.
        payload_bits=bits+1
        row=audit.setdefault(address,dict(events=0,struct_bits=0,property_payload_bits=0,max_property_payload_bits=0,
            profiler_u16_bits=0,counter_overflow_events=0,newest_base_dynamic_peak_by_region={},payload_sequence=[]))
        row['events']+=1;row['struct_bits']+=bits;row['property_payload_bits']+=payload_bits
        row['max_property_payload_bits']=max(row['max_property_payload_bits'],payload_bits)
        row['profiler_u16_bits']+=payload_bits&65535;row['counter_overflow_events']+=payload_bits>65535
        row['payload_sequence'].append(payload_bits)
        row['newest_base_dynamic_peak_by_region'][region]=max(row['newest_base_dynamic_peak_by_region'].get(region,0),base)
    for conn in measured:
        conn['serializer_audit']=audit.get(conn['address'])
        if conn['serializer_audit']:
            payloads=conn['serializer_audit'].pop('payload_sequence')
            observed=next(row['visual_updates'] for index,row in connections.items() if index is not None and addresses[index]==conn['address'])
            conn['serializer_audit']['profiler_sequence_matches']= [p&65535 for p in payloads]==[v['bits'] for v in observed]
            if not conn['serializer_audit']['profiler_sequence_matches']:
                conn['serializer_audit']['sequence_mismatch']=dict(writer_events=len(payloads),profiler_events=len(observed),
                    first_differences=[dict(index=i,writer_modulo=p&65535,profiler_bits=v['bits'])
                        for i,(p,v) in enumerate(zip(payloads,observed)) if (p&65535)!=v['bits']][:8])
            if conn['serializer_audit']['profiler_sequence_matches']:
                for initial,key in ((True,'visual_grid_initial'),(False,'visual_grid_delta')):
                    values=[p for p,v in zip(payloads,observed) if v['initial']==initial]
                    conn[key]['actual_payload_bits']=sum(values)
                    conn[key]['max_actual_payload_bits']=max(values,default=0)
            conn['mean_visual_grid_payload_bytes_equivalent_per_second']=conn['serializer_audit']['property_payload_bits']/8/max(.001,conn['active_seconds'])
    ground_audit={}
    for match in re.finditer(r'\[EcoPatchGroundNet\] Conn=(\S+) Region=(\S+) Bits=(\d+)',text):
        address,region,bits=match.groups()
        ground_audit.setdefault(address,[]).append(int(bits)+1)
    for conn in measured:
        payloads=ground_audit.get(conn['address'],[])
        observed=next(row['ground_updates'] for index,row in connections.items() if index is not None and addresses[index]==conn['address'])
        conn['patch_ground_audit']=dict(events=len(payloads),actual_payload_bits=sum(payloads),
            max_actual_payload_bits=max(payloads,default=0),counter_overflow_events=sum(p>65535 for p in payloads),
            profiler_sequence_matches=[p&65535 for p in payloads]==[v['bits'] for v in observed],
            initial_payload_bits=sum(p for p,v in zip(payloads,observed) if v['initial']),
            delta_payload_bits=sum(p for p,v in zip(payloads,observed) if not v['initial']))
    relevance=json.loads((run/'Relevance.json').read_text(encoding='utf-8-sig'))
    checks=dict(network_regressions=relevance['passed'],complete_stream=eos,
        two_field_connections=len(measured)==2,
        initial_and_delta=all(c['visual_grid_initial']['events']>0 and c['visual_grid_delta']['events']>0 for c in measured),
        serializer_audit_present=all(c['serializer_audit'] for c in measured),
        profiler_matches_writer_modulo_u16=all(c['serializer_audit'] and c['serializer_audit']['profiler_u16_bits']==c['raw_profiler_field_property_bits'].get('VisualGrid') for c in measured),
        profiler_sequence_matches=all(c['serializer_audit'] and c['serializer_audit']['profiler_sequence_matches'] for c in measured),
        patch_ground_sequence_matches=all(c['patch_ground_audit']['profiler_sequence_matches'] for c in measured),
        socket_covers_field_payload=all(c['serializer_audit'] and c['socket_sent_bytes']*8>=c['serializer_audit']['property_payload_bits']+
            c['patch_ground_audit']['actual_payload_bits']+
            sum(bits for name,bits in c['raw_profiler_field_property_bits'].items() if name not in ('VisualGrid','PatchGround')) for c in measured))
    report=dict(profile=str(paths[0].relative_to(root)),version=version,game=game,url=url,
        duration_seconds=frames[-1]-frames[0],frames=len(frames),tokens=tokens,connections=report_connections,
        field_classes={name:count for name,count in classes.items() if name in field_class_names},
        checks=checks,passed=all(checks.values()),
        scope='Server outgoing socket payload bytes per connection; VisualGrid/PatchGround serialization bits before packetization',
        relevance_scope=relevance.get('scope','Legacy vegetation/life/camera circuit'),
        limitations=['No IP/UDP/link headers or packet capture; socket totals include all actors, RPCs and protocol traffic',
            'Field property bits exclude shared packet/bunch/actor headers, retransmissions and packet-handler overhead',
            'Initial flag is actor/channel initial replication, including relevance re-entry; delta does not guarantee few changed cells',
            'Profiler property counters are uint16; use the writer audit to detect overflow instead of assuming counters are complete',
            'Newest base dynamic bytes count excludes object size, ACK/history-retained states, channels, shared shadows and allocator overhead',
            'No complete connection memory measurement or deployment budget guarantee'])
    (run/'NetworkProfileSummary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)

if sys.argv[1:2]==['--grass-network']:
    if len(sys.argv)!=3:raise SystemExit('Usage: --grass-network SavedFolder')
    summarize_grass_network(sys.argv[2]);raise SystemExit(0)

def summarize_grass_profile(folder):
    """Summarize opt-in CSV timings without presenting a local baseline as a release budget."""
    if not re.fullmatch(r'[A-Za-z0-9_]+', folder):
        raise ValueError('Simple Saved folder name required')
    run = root / 'Saved' / folder
    runtime = json.loads((run / 'PIE_Runtime.json').read_text(encoding='utf-8-sig'))
    if runtime['result'] != 'FINISHED' or not runtime.get('grass_profile'):
        raise ValueError('A finished GrassProfile run is required')
    path = root / 'Saved/Profiling/CSV' / ('EcosystemLife_' + folder + '_PIE.csv')
    columns, metadata = {}, {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        footer = deque(csv.reader(stream), maxlen=2)
        if len(footer) != 2 or footer[-1][:2] != ['[HasHeaderRowAtEnd]', '1']:
            raise ValueError('CSV footer missing: asynchronous capture did not finish')
        # UE appends new stat columns during capture; its final header covers all frames.
        header = footer[0]
        metadata = dict(zip(footer[1][::2], footer[1][1::2]))
        stream.seek(0)
        rows = csv.reader(stream)
        next(rows)
        for row in rows:
            if row and row[0] == '[HasHeaderRowAtEnd]':
                metadata = dict(zip(row[::2], row[1::2]))
                continue
            if len(row) > len(header): continue
            for key, value in zip(header, row):
                if not (key.startswith('EcoGrass/') or key == 'FrameTime'): continue
                try: number = float(value)
                except ValueError: continue  # UE repeats its header at capture end.
                if math.isfinite(number): columns.setdefault(key, []).append(number)
    def stats(values):
        values = sorted(values)
        return dict(samples=len(values), mean=sum(values)/len(values),
                    p95=values[math.ceil(.95*len(values))-1], maximum=values[-1]) if values else None
    timings = {key: dict(unit='traces' if key.endswith('Traces') else 'ms',
                        all_frames=stats(values), active_frames=stats([v for v in values if v > 0]))
               for key, values in columns.items()}
    patch_layout = runtime.get('patch_layout', False)
    required = ('EcoGrass/GameThread/RefreshVisuals', 'EcoGrass/GameThread/GatherGround',
                'EcoGrass/GameThread/PublishCells', 'EcoGrass/PatchGroundTraces' if patch_layout else 'EcoGrass/CandidateTraces')
    if any(not columns.get(key) for key in required):
        raise ValueError('Missing EcoGrass CSV columns: ' + str(list(columns)))
    regions = {}
    memory_keys = ('visual_grid_allocated_bytes', 'candidate_cache_allocated_bytes',
                   'ground_cache_allocated_bytes', 'movement_marks_allocated_bytes', 'native_food_grid_buffer_bytes')
    # Old evidence has no patch allocations; do not silently manufacture measurements for it.
    memory_keys += tuple(key for key in ('layout_sample_cache_allocated_bytes', 'patch_ground_dto_allocated_bytes',
        'native_patch_static_allocated_bytes') if all(key in f for s in runtime['samples'] for f in s['fields']))
    for sample in runtime['samples']:
        for field in sample['fields']:
            region = regions.setdefault(field['region'], dict(max_instances=0, max_cached_candidates=0,
                candidate_limit=0, trace_limit_per_refresh=0, peak_allocations={key: 0 for key in memory_keys}))
            region['max_instances'] = max(region['max_instances'], field['instances'])
            region['max_cached_candidates'] = max(region['max_cached_candidates'], field['cached_candidates'])
            region['candidate_limit'] = max(region['candidate_limit'], field['local_candidate_limit'])
            region['trace_limit_per_refresh'] = max(region['trace_limit_per_refresh'], field['candidate_trace_limit_per_refresh'])
            for key in memory_keys:
                region['peak_allocations'][key] = max(region['peak_allocations'][key], field[key])
    all_fields = [field for sample in runtime['samples'] for field in sample['fields']]
    checks = dict(ledger_matches=all(abs(f['food']-f['ledger_amount']) < 1e-6 for f in all_fields),
        capture_duration_complete=float(metadata.get('[captureduration]', 0)) >= runtime['duration_wall_seconds'] - 8,
        candidates_bounded=all(r['max_instances'] <= r['max_cached_candidates'] <= r['candidate_limit'] for r in regions.values()),
        traces_bounded=(all(a+b <= 96 for a,b in zip(columns.get('EcoGrass/PatchGroundTraces', []),
                columns.get('EcoGrass/PatchCellGroundTraces', [])))
            and bool(columns.get('EcoGrass/PatchCellGroundTraces')) if patch_layout
            else max(columns['EcoGrass/CandidateTraces']) <= sum(r['trace_limit_per_refresh'] for r in regions.values())),
        renders=any(r['max_instances'] > 0 for r in regions.values()),
        no_screenshots=runtime['screenshots'] == 0,
        no_agent_dumps=all(not s['agents'] for s in runtime['samples']))
    report = dict(csv=str(path.relative_to(root)), scenario=runtime['fixture'], checks=checks,
        passed=all(checks.values()), timings=timings, regions=regions,
        capture_duration_seconds=float(metadata.get('[captureduration]', 0)),
        peak_total_instances=max(sum(f['instances'] for f in s['fields']) for s in runtime['samples']),
        peak_total_allocations={key: max(sum(f[key] for f in s['fields']) for s in runtime['samples']) for key in memory_keys},
        hardware={key: metadata.get('['+key+']') for key in ('cpu','gpu','systemresolution.resx','systemresolution.resy','rhiname')},
        scope='Standalone Editor PIE, one observer, all Field scopes summed per frame; active frames exclude zero values',
        limitations=['Local baseline only; no production frame budget or before/after improvement established',
            'Container allocations exclude shared assets, allocator overhead, ISM CPU/render/GPU buffers and replication connections',
            'CSV system resolution is recorded; the separate PIE viewport resolution was not measured',
            'No wire bandwidth, World Partition unload or multi-client performance acceptance in this run'])
    (run / 'ProfileSummary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['passed']: raise SystemExit(1)

if sys.argv[1:2] == ['--grass-profile']:
    if len(sys.argv) != 3: raise SystemExit('Usage: --grass-profile SavedFolder')
    summarize_grass_profile(sys.argv[2])
    raise SystemExit(0)

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

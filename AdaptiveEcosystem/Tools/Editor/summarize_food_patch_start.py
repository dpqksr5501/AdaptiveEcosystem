"""S0/S1 evidence only. Does not label anchor-only work as completed grazing or formal S6."""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def folder(value):
    if not re.fullmatch(r'[A-Za-z0-9_]+', value):
        raise argparse.ArgumentTypeError('Use a simple Saved folder name')
    return value

def read(run, name):
    return json.loads((ROOT / 'Saved' / run / name).read_text(encoding='utf-8-sig'))

def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('profile_before', 'profile_after', 'network_before', 'network_after', 'output'):
        parser.add_argument('--'+name.replace('_','-'), type=folder, required=True)
    args = parser.parse_args()
    before, after = [read(run, 'ProfileSummary.json') for run in (args.profile_before,args.profile_after)]
    networks = [read(run,'NetworkProfileSummary.json') for run in (args.network_before,args.network_after)]
    auto = read('FoodPatchGrazing_20261108_S0','S1_WireAutomation/index.json')
    key = 'EcoGrass/GameThread/RefreshVisuals'
    p95_before, p95_after = [s['timings'][key]['active_frames']['p95'] for s in (before,after)]
    source_paths = ['Core/EcoFoodPatchLayout.h','Core/EcoFoodPatchLayout.cpp','World/EcoVegetationField.h',
        'World/EcoVegetationField.cpp','AI/Policy/EcoPolicyV3IntegratedSubsystem.h',
        'AI/Policy/Tests/EcoFoodPatchLayoutTest.cpp','Creature/Runtime/EcoEcosystemCheckpoint.cpp']
    sources = {p: hashlib.sha256((ROOT/'Source/AdaptiveEcosystem'/p).read_bytes()).hexdigest() for p in source_paths}
    binary = ROOT/'Binaries/Win64/UnrealEditor-AdaptiveEcosystem.dll'
    binary_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest() if binary.is_file() else None
    actual_counts=[]
    for run in (args.profile_before,args.profile_after,args.network_before,args.network_after):
        name='Server.log' if run in (args.network_before,args.network_after) else 'PIE.log'
        log=(ROOT/'Saved'/run/name).read_text(encoding='utf-8-sig',errors='replace')
        values=[int(v) for v in re.findall(r'\[Eco Integration\] NetMode=[01] LogicalOwned=(\d+)',log)]
        actual_counts.append(dict(run=run,logical_owned_min=min(values) if values else None,
            logical_owned_max=max(values) if values else None,scope='Logged owned logical entities, including lifecycle; not a fixed live-deer count'))
    command = ['git','-c','filter.lfs.process=','-c','filter.lfs.required=false']
    def git(*parts):
        return subprocess.check_output(command+list(parts),cwd=ROOT,text=True,encoding='utf-8',errors='replace').strip()
    report = dict(created_kst=datetime.now(timezone(timedelta(hours=9))).isoformat(),
        scope='S0 legacy cell consumption versus S1 shared layout/anchors only; S2-S6 incomplete',
        commit=git('rev-parse','HEAD'),branch=git('branch','--show-current'),dirty_worktree=True,
        working_tree_stat_including_preexisting_edits=git('diff','--stat'),source_sha256=sources,
        final_runtime_binary_sha256=binary_sha256,actual_population_log_ranges=actual_counts,
        baseline_binary_hash=None,baseline_binary_note='Preimplementation S0 capture completed before edits; its binary hash was not recorded',
        profile_runs=[args.profile_before,args.profile_after],profile_checks=[s['checks'] for s in (before,after)],
        render_refresh_active_frame_p95_ms=dict(before=p95_before,after=p95_after,
            percent_change=(p95_after/p95_before-1)*100),
        frame_p95_ms=[s['timings']['FrameTime']['all_frames']['p95'] for s in (before,after)],
        container_peak_bytes=[s['peak_total_allocations'] for s in (before,after)],
        automation={k:auto[k] for k in ('succeeded','succeededWithWarnings','failed','notRun')},
        network_runs=[args.network_before,args.network_after],network_checks=[n['checks'] for n in networks],
        network_validation_scopes=[n.get('relevance_scope') for n in networks],
        network_connections=[[dict(address=c['address'],socket_mean_bytes_per_s=c['mean_socket_bytes_per_second'],
            cell_serializer=c.get('serializer_audit'),ground_serializer=c.get('patch_ground_audit'))
            for c in n['connections'] if c['field_actor_calls']] for n in networks],
        correctness_acceptance={f'F{i:02d}':'not completed; requires S2-S6' for i in range(1,13)},
        formal_budget_qualified=False,
        limitations=['One seed/short local captures; not warmup30+180sec x3 seeds or 30-minute soak',
            'S1 cost is not the full patch grazing B mode; no improvement claim or full CPU/GPU budget acceptance',
            'Native step stage percentiles, GPU/ISM buffers, full replication history memory and packet capture remain unmeasured',
            'Food-patch-specific network scope excludes legacy camera circuit/life acceptance; original failed gates are retained',
            'Integrated S1 supports 1..9 patches per cell; 10..25 require S4 initial snapshot budget/chunking',
            'Animation mouth alignment, automatic terrain streaming invalidation and checkpoint S5 are incomplete'])
    report['evidence_checks_passed'] = all(s['passed'] for s in (before,after)) and all(n['passed'] for n in networks) and auto['failed']==auto['notRun']==0
    target = ROOT/'Saved'/args.output
    target.mkdir(parents=True,exist_ok=True)
    (target/'Manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('evidence_checks_passed','formal_budget_qualified','render_refresh_active_frame_p95_ms','automation')},indent=2))
    if not report['evidence_checks_passed']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()

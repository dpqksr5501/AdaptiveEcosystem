"""Actual authority life-v1 observation and cross-process checkpoint validation.

No synthetic feeding, population, genome, weather or movement writes. Load mode
performs the explicit restore operation under test. Separate fixtures test combat.
"""
import hashlib,json,re,time,sys
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ecosystem_observation import capture_life,checkpoint_digest

cmd=unreal.SystemLibrary.get_command_line()
def arg(key,default):
    found=re.search(r'-'+key+r'=([^\s"]+)',cmd,re.I)
    return found.group(1) if found else default
mode=arg('LifeAuditMode','observe')
name=arg('LifeAuditName',mode)
duration=float(arg('LifeAuditDuration','120'))
save_at=float(arg('LifeAuditSaveAt','75'))
simulation_duration=float(arg('LifeAuditSimulationSeconds','0'))
sample_seconds=float(arg('LifeAuditSampleSeconds','5'))
if not 1<=sample_seconds<=60:raise RuntimeError('Bounded sample interval required')
csv_enabled='-lifeauditcsv' in cmd.lower()
slot=arg('LifeAuditSlot','LifeRestart')
life_expected=arg('EcoEcosystemLife','1')!='0'
drought_region=arg('LifeAuditDrought','')
if drought_region and (mode!='observe' or drought_region not in ('Barren','Forest','Highland')):raise RuntimeError('Unsupported drought fixture')
if mode not in ('observe','save','load') or not re.fullmatch(r'[A-Za-z0-9_]+',name):raise RuntimeError('Unsupported audit mode/name')
root=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
out=root/'EcosystemLife_20261023';out.mkdir(parents=True,exist_ok=True)
world=next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name()=='LV_JYU_Ecosystem' and unreal.GameplayStatics.get_game_state(w) is not None),None)
if world is None:raise RuntimeError('Active ecosystem game world required')
runtime=next(iter(unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoCreatureIntegrationSpawner)),None)
if runtime is None:raise RuntimeError('Authority completion relay required')
state={'started':None,'next':0,'samples':[],'operation':None,'error':None,'first_step':None}
deadline=time.monotonic()+duration+150

def capture():
    return capture_life(world)

def digest(row):
    return checkpoint_digest(row)

def finish(result):
    runtime.on_runtime_sample.remove_callable(tick)
    if csv_enabled:unreal.SystemLibrary.execute_console_command(world,'csvprofile STOP')
    all_agents={a['stable_id']:a for s in state['samples'] for a in s['agents']}
    children=[a for a in all_agents.values() if a.get('life',{}).get('origin')==1]
    report={'result':result,'mode':mode,'error':state['error'],'operation':state['operation'],'samples':state['samples'],
        'natural_child_ids':sorted(a['stable_id'] for a in children),
        'fixture':('EXPLICIT development drought: '+drought_region+' food loss with M4 habitat receipt, regeneration suspended; not natural ecology' if drought_region else 'none; authored climate and actual authority outcomes')}
    report['fixed_step_simulation_target']=simulation_duration
    report['seed']=int(arg('EcoV3Seed','23'))
    report['ecosystem_life_enabled']=life_expected
    report['fixed_step_benchmark']='-benchmark' in cmd.lower()
    report['alive_at_end']=sum(a.get('hp',0)>0 for a in state['samples'][-1]['agents']) if state['samples'] else 0
    (out/(name+'_Life.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('ECOSYSTEM_LIFE_AUDIT_'+result+' '+json.dumps({'mode':mode,'samples':len(state['samples']),'children':len(children)}))
    if '-lifeauditquitonfinish' in cmd.lower() and not csv_enabled:unreal.SystemLibrary.execute_console_command(world,'QUIT')

def tick(dt):
    try:
        if time.monotonic()>deadline:raise RuntimeError('Authority initialization/audit deadline')
        if not runtime.is_runtime_ready():return
        row=capture()
        if (not row['agents'] and state['started'] is None) or len(row['fields'])!=3 or (life_expected and any('life' not in a for a in row['agents'])):return
        now=time.monotonic()
        if state['started'] is None:
            state['started']=now;state['first_step']=row['fields'][0]['native_step']
            if drought_region:
                migration=next((m for m in unreal.ObjectIterator(unreal.EcoHerdMigrationSubsystem) if m.get_outer()==world),None)
                if migration is None or not migration.apply_food_fraction_for_audit(drought_region,0,True):raise RuntimeError('Explicit drought transaction rejected')
                row=capture()
            if csv_enabled:
                unreal.SystemLibrary.execute_console_command(world,'csvprofile STARTFILE=EcosystemLife_'+name+'.csv')
                unreal.SystemLibrary.execute_console_command(world,'csvprofile START')
        elapsed=now-state['started']
        simulation_elapsed=(row['fields'][0]['native_step']-state['first_step'])*2/15
        if mode=='load' and state['operation'] is None:
            expected=json.loads((out/(slot+'_Expected.json')).read_text(encoding='utf-8'))
            before=digest(row)
            # Missing/unsupported input must be rejected before any live state changes.
            if runtime.load_ecosystem('MissingCheckpoint_NoAutoReset'):raise AssertionError('Missing save accepted')
            if digest(capture())!=before:raise AssertionError('Rejected load mutated the world')
            original=(root/'Ecosystem'/(slot+'.eco')).read_bytes()
            for suffix,index in (('_BadChecksum',12),('_BadVersion',4)):
                bad=bytearray(original);bad[index]^=127
                (root/'Ecosystem'/(slot+suffix+'.eco')).write_bytes(bad)
                if runtime.load_ecosystem(slot+suffix):raise AssertionError('Invalid save accepted '+suffix)
                if digest(capture())!=before:raise AssertionError('Invalid save changed live state '+suffix)
            if not runtime.load_ecosystem(slot):raise RuntimeError('Real checkpoint restore rejected; inspect the first native reason')
            restored=digest(capture())
            if restored!=expected:
                (out/(name+'_RestoreMismatch.json')).write_text(json.dumps({'expected':expected,'actual':restored},indent=2),encoding='utf-8')
                raise AssertionError('Exact restored individual/soil/ledger state differs')
            state['operation']={'restored_exactly':True,'rejected_load_unchanged':True,'agents':len(restored['agents'])}
            row=capture()
        if mode=='save' and elapsed>=save_at and state['operation'] is None:
            expected=digest(row)
            if not runtime.save_ecosystem(slot):
                state['save_attempts']=state.get('save_attempts',0)+1
                if state['save_attempts']>=5:raise RuntimeError('Real checkpoint write rejected repeatedly; inspect first native reason')
                return
            (out/(slot+'_Expected.json')).write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8')
            file=root/'Ecosystem'/(slot+'.eco')
            state['operation']={'saved':True,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'agents':len(expected['agents'])}
            learning={'schema':'ecosystem-life-v1-evaluation','training_ready':False,'runtime_python_inference':False,
                'policy_contract':'existing V1 7/4 and v3 18/5 mask2 unchanged; optional v3 21/5 remains separate',
                'checkpoint_sha256':state['operation']['sha256'],'agents':row['agents'],
                'regions':[json.loads(f.capture_diagnostics(True)) for f in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoVegetationField)]}
            (out/(slot+'_LearningSnapshot.json')).write_text(json.dumps(learning,ensure_ascii=False,indent=2),encoding='utf-8')
        if mode=='save' and state['operation'] and elapsed>=save_at+8 and not state['operation'].get('live_rollback_rejected'):
            before=digest(capture())
            if runtime.load_ecosystem(slot):raise AssertionError('Unsupported live rollback was accepted')
            if digest(capture())!=before:raise AssertionError('Rejected live rollback changed live state')
            state['operation']['live_rollback_rejected']=True
        progress=simulation_elapsed if simulation_duration else elapsed
        if progress>=state['next']:
            state['next']=progress+sample_seconds;row['elapsed']=elapsed;row['simulation_elapsed']=simulation_elapsed;state['samples'].append(row)
            for f in row['fields']:
                for a,b in (('food','ledger_amount'),('consumed','ledger_consumed'),('grown','ledger_grown'),('environment_lost','ledger_environment_lost')):
                    if abs(f[a]-f[b])>1e-5:raise AssertionError('Authority resource mismatch '+a)
            (out/(name+'_Progress.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
        if (simulation_duration and simulation_elapsed>=simulation_duration) or (not simulation_duration and elapsed>=duration):
            if mode!='observe' and state['operation'] is None:raise AssertionError('Requested checkpoint operation did not occur')
            if not state['samples'] or row['fields'][0]['native_step']!=state['samples'][-1]['fields'][0]['native_step']:
                row['elapsed']=elapsed;row['simulation_elapsed']=simulation_elapsed;state['samples'].append(row)
            finish('FINISHED')
    except Exception as error:
        state['error']=repr(error);unreal.log_error('ECOSYSTEM_LIFE_AUDIT_ERROR '+repr(error));finish('FAILED')

runtime.on_runtime_sample.add_callable(tick)
unreal.log('ECOSYSTEM_LIFE_AUDIT_BOUND '+mode)

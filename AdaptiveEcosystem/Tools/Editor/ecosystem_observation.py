"""Shared read-only QA capture; never an inference or runtime gameplay dependency."""
import json
import unreal

def capture_life(world):
    agents=[]
    for key in unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(world):
        raw=unreal.EcoCreatureInspectionLibrary.capture_agent(world,key)
        if isinstance(raw,tuple):raw=next((v for v in raw if isinstance(v,str)),None)
        if raw:agents.append(json.loads(raw))
    fields=[json.loads(a.capture_diagnostics()) for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoVegetationField)]
    native=next((n for n in unreal.ObjectIterator(unreal.EcoPolicyV3IntegratedSubsystem) if n.get_outer()==world),None)
    if native is None:raise RuntimeError('Active native subsystem missing')
    return dict(agents=agents,fields=fields,performance=json.loads(native.capture_step_performance()))

def checkpoint_digest(row):
    agent_keys=('stable_id','species','region','hp','energy','native_world_position','life','regional_known_human_danger')
    field_keys=('region','food','grown','environment_lost','consumed','mean_moisture','native_step','ledger_amount','ledger_consumed','ledger_grown','ledger_environment_lost','receipt_sequence')
    # A just-restored corpse's deferred AliveTag removal can await the next phase.
    # Population comparisons use the authoritative HP, not that transient tag.
    return dict(agents=sorted([{k:a[k] for k in agent_keys if k in a} for a in row['agents'] if a.get('hp',0)>0],key=lambda a:int(a['stable_id'])),
        fields=sorted([{k:f[k] for k in field_keys if k in f} for f in row['fields']],key=lambda f:f['region']))

def write_checkpoint_sample(world,runtime,out,slot):
    row=capture_life(world);expected=checkpoint_digest(row)
    if not runtime.save_ecosystem(slot):raise RuntimeError('Observed-experience checkpoint rejected')
    (out/(slot+'_Expected.json')).write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8')
    snapshot=dict(schema='ecosystem-life-v1-evaluation',training_ready=False,runtime_python_inference=False,agents=row['agents'],
        regions=[json.loads(f.capture_diagnostics(True)) for f in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoVegetationField)])
    (out/(slot+'_LearningSnapshot.json')).write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(slot=slot,agents=len(expected['agents']))

"""Second owned map: same runtime, unrelated region IDs, three actual ground heights.
No team map edits. This is a small capability fixture, not production acceptance.
"""
import json,time,traceback,re
from pathlib import Path
import unreal

TARGET='/Game/JYU/Maps/LV_JYU_HabitatTransferFixture'
SOURCE='/Game/JYU/Maps/LV_JYU_Ecosystem'
OWNER='JYU.Ecosystem.NaturalHabitat.20261030'
folder_match=re.search(r'-HabitatTransferAuditFolder=([A-Za-z0-9_]+)(?:\s|$)',unreal.SystemLibrary.get_command_line())
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/(folder_match.group(1) if folder_match else 'NaturalHabitatRelease_20261030')
out.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets=unreal.EditorAssetLibrary
report={'result':'RUNNING','map':TARGET,'fixture':'Three disconnected tagged solid platforms; no journeys; no predators; static authored climate','samples':[]}
start=None;deadline=time.monotonic()+150;next_sample=0

def create():
    if assets.does_asset_exist(TARGET):
        if not levels.load_level(TARGET):raise RuntimeError('Fixture level unavailable')
        a=editor.get_editor_world()
        if assets.get_metadata_tag(a,'JYUOwner')!=OWNER:raise RuntimeError('Existing fixture is not owned')
        return
    if not levels.load_level(SOURCE):raise RuntimeError('Missing source configurations')
    source=next(a for a in actors.get_all_level_actors() if isinstance(a,unreal.EcoCreatureIntegrationSpawner))
    props={p:source.get_editor_property(p) for p in ('herbivore_config','wolf_config','herbivore_actor_class','wolf_actor_class','vegetation_field_class','natural_habitat_profile')}
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    world=editor.get_editor_world()
    settings=world.get_world_settings()
    settings.set_editor_property('default_game_mode',unreal.EcoCreatureIntegrationGameMode)
    runtime=actors.spawn_actor_from_class(unreal.EcoCreatureIntegrationSpawner,unreal.Vector(0,0,100))
    for p,v in props.items():runtime.set_editor_property(p,v)
    for p,v in {'use_v3_policy':True,'enable_vegetation':True,'enable_ecosystem_life':True,'enable_herd_journeys':False,
                'use_habitat_streaming':False,'v3_deer_per_region':8,'global_population_limit':64,'host_visual_distance':0.}.items():runtime.set_editor_property(p,v)
    groups=[];profiles={}
    for index,(region_id,kind,z,temp) in enumerate((('TransferMeadow','TemperateMosaic',0.,20.),('TransferDunes','Dryland',2500.,32.),('TransferSummit','Alpine',6000.,-5.))):
        x=(index-1)*30000.
        floor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(x,0,z-50))
        floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
        floor.set_actor_scale3d(unreal.Vector(240,240,1))
        floor.static_mesh_component.set_collision_profile_name('BlockAll')
        floor.set_editor_property('tags',['Eco.VegetationGround'])
        region=actors.spawn_actor_from_class(unreal.EcologyRegion,unreal.Vector(x,0,z))
        region.set_editor_property('region_id',region_id)
        region.get_editor_property('region_bounds').set_box_extent(unreal.Vector(12000,12000,800),False)
        region.set_editor_property('initial_food_amount',1000.);region.set_editor_property('food_capacity',2000.)
        region.set_editor_property('food_regeneration_rate',8.)
        env=region.get_environment_state();env.set_editor_property('temperature',temp);env.set_editor_property('rainfall',.25)
        region.set_environment_state(env)
        group=unreal.EcoCreatureSpawnGroup();group.set_editor_property('region_id',region_id)
        group.set_editor_property('herbivores',8);group.set_editor_property('wolves',0)
        groups.append(group)
        profile=unreal.load_asset('/Game/JYU/Ecosystem/Natural/DA_JYU_Habitat_'+kind);profiles[region_id]=profile
        habitat=actors.spawn_actor_from_class(unreal.EcoVegetationHabitat,unreal.Vector(x,0,z))
        for p,v in {'region_id':region_id,'habitat_id':region_id+'_Soil','growth_profile':profile,'priority':10}.items():habitat.set_editor_property(p,v)
        habitat.get_editor_property('bounds').set_box_extent(unreal.Vector(11000,11000,400),False)
        if index==0:
            water=actors.spawn_actor_from_class(unreal.EcoVegetationHabitat,unreal.Vector(x+1500,1500,z))
            for p,v in {'region_id':region_id,'habitat_id':'TransferFreshwater','growth_profile':profile,'priority':100,
                        'plant':1,'connected_fresh_water':True,'water_surface_z':z+25.}.items():water.set_editor_property(p,v)
            water.get_editor_property('bounds').set_box_extent(unreal.Vector(1500,1500,200),False)
    runtime.set_editor_property('groups',groups);runtime.set_editor_property('region_habitat_profiles',profiles)
    assets.set_metadata_tag(world,'JYUOwner',OWNER)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world,TARGET):raise RuntimeError('Fixture save failed')

def finish(result,error=None):
    report.update(result=result,error=error)
    (out/'TransferFixture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('NATURAL_TRANSFER_'+result+' '+str(error))
    unreal.unregister_slate_post_tick_callback(handle)
    levels.editor_request_end_play();unreal.SystemLibrary.quit_editor()

def tick(dt):
    global start,next_sample
    try:
        if time.monotonic()>deadline:raise RuntimeError('Fixture observation deadline')
        game=editor.get_game_world()
        if not game:return
        runtimes=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoCreatureIntegrationSpawner)
        if not runtimes or not runtimes[0].is_runtime_ready():return
        now=time.monotonic()
        if start is None:start=now
        elapsed=now-start
        if elapsed<next_sample:return
        next_sample=elapsed+10
        fields=[json.loads(f.capture_diagnostics(True)) for f in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.EcoVegetationField)]
        agents=[]
        for key in unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(game):
            raw=unreal.EcoCreatureInspectionLibrary.capture_agent(game,key)
            if isinstance(raw,tuple):raw=next((v for v in raw if isinstance(v,str)),None)
            if raw:agents.append(json.loads(raw))
        report['samples'].append(dict(elapsed=elapsed,fields=fields,agents=agents))
        if elapsed>=35:
            expected={'TransferMeadow':('TemperateMosaic',0),'TransferDunes':('Dryland',2500),'TransferSummit':('Alpine',6000)}
            if len(fields)!=3 or len(agents)<24:raise RuntimeError('Missing fields/agents')
            for f in fields:
                if f['natural_profile']!=expected[f['region']][0] or f['ground_sites']<100:raise RuntimeError('Profile or actual-ground reuse failed')
            for a in agents:
                if abs(a['native_world_position'][2]-expected[a['region']][1])>60:raise RuntimeError('Native body on wrong ground height')
            finish('FINISHED')
    except Exception:finish('FAILED',traceback.format_exc())

try:
    create()
    world=editor.get_editor_world()
    runtime=next(a for a in actors.get_all_level_actors() if isinstance(a,unreal.EcoCreatureIntegrationSpawner))
    report['authoring']=json.loads(runtime.capture_habitat_authoring_report())
    # The authoring report must consume the same regional wading limit as movement.
    # Change only the in-memory value before PIE and restore it without saving assets.
    profile=runtime.get_editor_property('region_habitat_profiles')['TransferMeadow']
    old_depth=profile.get_editor_property('max_wading_depth_cm')
    try:
        profile.set_editor_property('max_wading_depth_cm',10.)
        shallow=json.loads(runtime.capture_habitat_authoring_report())
        report['custom_wading_limit_detected']=shallow['deep_water_samples']>report['authoring']['deep_water_samples']
        if not report['custom_wading_limit_detected']:raise RuntimeError('Authoring report ignored custom regional wading limit')
    finally:profile.set_editor_property('max_wading_depth_cm',old_depth)
    # A path on the lower platform cannot reach an arbitrary upper Z at the same XY.
    report['unreachable_height_rejected']=not unreal.EcoCreatureAnimationBuilder.validate_habitat_ground_segment(world,unreal.Vector(-30000,0,0),unreal.Vector(-30000,0,600))
    if not report['unreachable_height_rejected']:raise RuntimeError('Endpoint height validation failed')
    levels.editor_request_begin_play()
    handle=unreal.register_slate_post_tick_callback(tick)
except Exception:
    report.update(result='FAILED',error=traceback.format_exc())
    (out/'TransferFixture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log_error(report['error']);unreal.SystemLibrary.quit_editor()

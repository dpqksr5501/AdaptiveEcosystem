"""Fresh-process reload checks, no asset/map writes."""
import json,re
from pathlib import Path
import unreal
target='/Game/JYU/Maps/LV_JYU_Ecosystem'
folder='/Game/JYU/Ecosystem/'
assets=unreal.EditorAssetLibrary
match=re.search(r'-EcosystemAssetAuditFolder=([A-Za-z0-9_]+)(?:\s|$)',unreal.SystemLibrary.get_command_line())
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/(match.group(1) if match else 'EcosystemBP_20261023')
out.mkdir(parents=True,exist_ok=True)
report={'b_blueprints':{},'weather':[],'habitats':[]}
for name in ('BP_JYU_VegetationField','BP_JYU_EcosystemWeather','BP_JYU_GrassHabitat','BP_JYU_MoistSoilHabitat','BP_JYU_ShrubHabitat','BP_JYU_RiparianHabitat'):
    bp=unreal.load_asset(folder+name);cls=assets.load_blueprint_class(folder+name)
    if not bp or not cls:raise RuntimeError('BP reload failed '+name)
    cdo=unreal.get_default_object(cls)
    report['b_blueprints'][name]=str(cls)
    if name=='BP_JYU_VegetationField':
        report['mesh']=str(cdo.get_editor_property('patch_mesh'))
        report['material']=str(cdo.get_editor_property('patch_material'))
        assert 'GrassA' in report['mesh'] and 'MI_JYU_EcosystemGrass' in report['material']
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(target):raise RuntimeError('Map reload failed')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world)
all_actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
report['legacy_visual_weather']=[a.get_path_name() for a in all_actors
    if a.get_class().get_name() in ('BP_WeatherManager_C','BP_WeatherManager_PlayerFollow_C')]
assert not report['legacy_visual_weather']
report['routes']=[dict(label=a.get_actor_label(),points=len(a.get_editor_property('points')),valid=a.is_valid_route())
    for a in all_actors if isinstance(a,unreal.EcoHerdMigrationRoute)]
assert report['routes'] and all(r['valid'] for r in report['routes'])
runtimes=[a for a in all_actors if isinstance(a,unreal.EcoCreatureIntegrationSpawner)]
assert len(runtimes)==1
runtime=runtimes[0]
report['map_opt_in']=runtime.get_editor_property('enable_vegetation')
report['life_opt_in']=runtime.get_editor_property('enable_ecosystem_life')
report['field_class']=str(runtime.get_editor_property('vegetation_field_class'))
assert report['map_opt_in'] and 'BP_JYU_VegetationField' in report['field_class']
for a in all_actors:
    if isinstance(a,unreal.EcoRegionEnvironmentAdapter):
        report['weather'].append(dict(label=a.get_actor_label(),region_ids=[str(v) for v in a.get_editor_property('region_ids')],
            cycle=a.get_editor_property('cycle_rainfall'),period=a.get_editor_property('rain_cycle_seconds'),offset=a.get_editor_property('rain_phase_offset_seconds')))
    if isinstance(a,unreal.EcoVegetationHabitat):
        report['habitats'].append(dict(label=a.get_actor_label(),region=str(a.get_editor_property('region_id')),plant=a.get_editor_property('plant'),
            drainage=a.get_editor_property('drainage'),shade=a.get_editor_property('shade'),connected_water=a.get_editor_property('connected_fresh_water'),
            extent=str(a.get_editor_property('bounds').get_unscaled_box_extent())))
assert len(report['weather'])==3 and all(w['cycle'] and w['period']==180 for w in report['weather'])
assert len(report['habitats'])==(10 if report['life_opt_in'] else 9)
if report['life_opt_in']:
    spring=assets.load_blueprint_class(folder+'BP_JYU_AuthoredSpring')
    assert spring
    report['b_blueprints']['BP_JYU_AuthoredSpring']=str(spring)
    connected=[a for a in all_actors if isinstance(a,unreal.EcoVegetationHabitat) and a.get_editor_property('connected_fresh_water')]
    assert len(connected)==1 and connected[0].is_valid_habitat()
    report['spring']=dict(region=str(connected[0].get_editor_property('region_id')),water_z=connected[0].get_editor_property('water_surface_z'))
report['rig_review']={}
for species,property_name in (('Herbivore','herbivore_actor_class'),('Wolf','wolf_actor_class')):
    cdo=unreal.get_default_object(runtime.get_editor_property(property_name))
    mesh=cdo.get_editor_property('visual_mesh');profile=cdo.get_editor_property('animation_profile')
    if mesh is None or profile is None:raise RuntimeError('Actual representation rig/profile required '+species)
    report['rig_review'][species]=dict(mesh=mesh.get_path_name(),skeleton=mesh.get_editor_property('skeleton').get_path_name(),
        morph_targets=[m.get_name() for m in mesh.get_editor_property('morph_targets')],
        foot_bones=[str(b) for b in profile.get_editor_property('foot_bones')],
        ik_end_bones=[str(b) for b in profile.get_editor_property('ik_end_bones')],
        ground_ik=profile.get_editor_property('enable_ground_ik'),
        shipped_shape_path='bounded uniform body scale; stride/speed compensation and existing foot IK',
        bone_proportion_authoring=False)
report['passed']=True
(out/'AssetReload.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('ECOSYSTEM_BP_RELOAD_PASSED')

"""Apply reusable natural-habitat profiles to the existing owned map only.
No map recreation, team map writes, vegetation/food refill, or world rule CVars.
"""
import json
from pathlib import Path
import unreal

TARGET='/Game/JYU/Maps/LV_JYU_Ecosystem'
FOLDER='/Game/JYU/Ecosystem/Natural'
OWNER='JYU.Ecosystem.NaturalHabitat.20261030'
assets=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
tools=unreal.AssetToolsHelpers.get_asset_tools()
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'NaturalHabitat_20261030'
out.mkdir(parents=True,exist_ok=True)
if not levels.load_level(TARGET):raise RuntimeError('Owned map unavailable')
world=editor.get_editor_world()
if not world.get_path_name().startswith(TARGET):raise RuntimeError('Map ownership boundary')
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Actual terrain not ready')
all_actors=actors.get_all_level_actors()
runtimes=[a for a in all_actors if isinstance(a,unreal.EcoCreatureIntegrationSpawner)]
if len(runtimes)!=1 or not runtimes[0].get_editor_property('enable_ecosystem_life'):raise RuntimeError('One existing life coordinator required')
habitats=[a for a in all_actors if isinstance(a,unreal.EcoVegetationHabitat)]
refuges=[a for a in all_actors if isinstance(a,unreal.EcoRefugeHabitat)]
if len(habitats)!=10 or not refuges:raise RuntimeError('Unexpected existing owned layout; review before authoring')
for a in habitats:
    if not a.get_actor_label().startswith('JYU_Ecosystem_'):raise RuntimeError('Unowned habitat '+a.get_path_name())
report=dict(map=TARGET,owner=OWNER,profiles=[],habitats=[],refuges=[],landscape_components=0)

def profile(name,kind):
    path=FOLDER+'/'+name
    if assets.does_asset_exist(path):
        asset=unreal.load_asset(path)
        if assets.get_metadata_tag(asset,'JYUOwner')!=OWNER:raise RuntimeError('Unowned profile '+path)
    else:
        factory=unreal.DataAssetFactory();factory.set_editor_property('data_asset_class',unreal.EcoNaturalHabitatProfile)
        asset=tools.create_asset(name,FOLDER,unreal.EcoNaturalHabitatProfile,factory)
        if not asset:raise RuntimeError('Profile creation failed')
    asset.set_editor_property('profile_id',kind)
    asset.set_editor_property('layout_seed',1907)
    asset.set_editor_property('cluster_scale_cm',1800.)
    asset.set_editor_property('wild_refuges',True)
    guilds=list(asset.get_editor_property('guilds'))
    mesh_names=['D','C','B']
    for i,g in enumerate(guilds):
        g.set_editor_property('mesh',unreal.load_asset('/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_Grass'+mesh_names[i]))
        if kind=='Dryland':
            g.set_editor_property('coverage',[.4,.8,.35][i])
            g.set_editor_property('moisture_min',[.15,.45,.08][i]);g.set_editor_property('moisture_max',[.65,.95,.55][i])
            g.set_editor_property('temperature_min',-3.);g.set_editor_property('temperature_optimum',24.);g.set_editor_property('temperature_max',52.)
            g.set_editor_property('height_cm',[25.,55.,65.][i])
        elif kind=='Alpine':
            g.set_editor_property('coverage',[.6,.8,.5][i])
            g.set_editor_property('temperature_min',-12.);g.set_editor_property('temperature_optimum',8.);g.set_editor_property('temperature_max',30.)
            g.set_editor_property('height_cm',[18.,35.,40.][i]);g.set_editor_property('max_slope_degrees',[35.,22.,35.][i])
    asset.set_editor_property('guilds',guilds)
    assets.set_metadata_tag(asset,'JYUOwner',OWNER)
    if not assets.save_loaded_asset(asset,only_if_is_dirty=False):raise RuntimeError('Profile save failed')
    report['profiles'].append(dict(path=path,kind=kind))
    return asset

profiles={key:profile('DA_JYU_Habitat_'+key,key) for key in ('TemperateMosaic','Dryland','Alpine')}
runtimes[0].set_editor_property('natural_habitat_profile',profiles['TemperateMosaic'])
runtimes[0].set_editor_property('region_habitat_profiles',{'Forest':profiles['TemperateMosaic'],'Barren':profiles['Dryland'],'Highland':profiles['Alpine']})
for a in habitats:
    label=a.get_actor_label();region=str(a.get_editor_property('region_id'))
    a.set_editor_property('habitat_id',label)
    connected=a.get_editor_property('connected_fresh_water')
    priority=100 if connected else 40 if 'MoistSoil' in label else 30 if 'Shrub' in label else 10
    a.set_editor_property('priority',priority);a.set_editor_property('blend_distance_cm',400. if not connected else 250.)
    variant='Dryland' if region=='Barren' else 'Alpine' if region=='Highland' else 'TemperateMosaic'
    a.set_editor_property('growth_profile',profiles[variant])
    if not connected:
        # Keep 3D bounds tied to this ground layer; avoid volumes spanning unrelated floors.
        b=a.get_editor_property('bounds');extent=b.get_unscaled_box_extent()
        b.set_box_extent(unreal.Vector(extent.x,extent.y,800.),False)
        a.set_actor_rotation(unreal.Rotator(0.,{'Grass':-13.,'Shrub':21.,'MoistSoil':8.}.get(label.split('_')[-1],0.),0.),False)
    report['habitats'].append(dict(id=label,region=region,profile=variant,priority=priority,connected_water=bool(connected)))
for ordinal,a in enumerate(sorted(refuges,key=lambda a:a.get_actor_label())):
    a.set_editor_property('natural_layout',True);a.set_editor_property('natural_boulder_count',0)
    a.set_editor_property('layout_seed',1907+ordinal*101)
    a.rebuild_habitat()
    report['refuges'].append(dict(label=a.get_actor_label(),seed=1907+ordinal*101,brush_instances=a.get_editor_property('brush').get_instance_count()))
if not levels.save_current_level():raise RuntimeError('Owned map save failed')
(out/'Authoring.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('NATURAL_HABITAT_AUTHORING_FINISHED '+TARGET)
unreal.SystemLibrary.quit_editor()

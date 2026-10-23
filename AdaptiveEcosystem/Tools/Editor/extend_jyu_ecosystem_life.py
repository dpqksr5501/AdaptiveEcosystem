"""Targeted changes to the existing owned ecosystem map. Never recreates the map."""
import json
from pathlib import Path
import unreal

TARGET='/Game/JYU/Maps/LV_JYU_Ecosystem'
FOLDER='/Game/JYU/Ecosystem'
OWNER='JYU.Ecosystem.LifeV1.20261023'
assets=unreal.EditorAssetLibrary
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'EcosystemLife_20261023'
out.mkdir(parents=True,exist_ok=True)
if not assets.does_asset_exist(TARGET):raise RuntimeError('Existing owned ecosystem map is required')
if not levels.load_level(TARGET):raise RuntimeError('Owned map load failed')
world=editor.get_editor_world()
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Terrain streaming failed')
all_actors=actors.get_all_level_actors()
runtimes=[a for a in all_actors if isinstance(a,unreal.EcoCreatureIntegrationSpawner)]
if len(runtimes)!=1:raise RuntimeError('One existing coordinator required')
runtime=runtimes[0]
if not runtime.get_editor_property('enable_vegetation'):raise RuntimeError('Do not replace the prior soil setup')
groups=runtime.get_editor_property('groups')
center=next(g.get_editor_property('food_patch_position') for g in groups if str(g.get_editor_property('region_id'))=='Forest')

def ground(point):
    result=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,point)
    if isinstance(result,unreal.Vector):return result
    if isinstance(result,tuple):
        if any(isinstance(v,bool) and not v for v in result):return None
        return next((v for v in result if isinstance(v,unreal.Vector)),None)
    return None

label='JYU_Ecosystem_Forest_AuthoredSpring'
existing=next((a for a in all_actors if a.get_actor_label()==label),None)
if existing and OWNER not in [str(t) for t in existing.get_editor_property('tags')]:raise RuntimeError('Spring label belongs to another author')
report={'map':TARGET,'source':'authored shallow spring, not a pre-existing river or a rainfall fixture','survey':[]}
if existing:
    spring=existing
    report['reused_owned_actor']=True
else:
    candidates=[]
    # Central strip between the previous grass/moist/shrub boxes; actual ground is
    # surveyed before assigning hydraulic head. Water is <=12cm over the minimum.
    for dy in (-3300,-2900,-2500):
        for dx in (-200,0,200):
            hint=center+unreal.Vector(dx,dy,0)
            points=[ground(hint+unreal.Vector(x,y,0)) for y in (-400,0,400) for x in (-400,0,400)]
            if not all(p is not None for p in points):continue
            lo,hi=min(p.z for p in points),max(p.z for p in points)
            row={'x':hint.x,'y':hint.y,'min_z':lo,'max_z':hi,'relief_cm':hi-lo}
            report['survey'].append(row)
            if hi-lo<=100:candidates.append((hi-lo,hint,lo,hi))
    if not candidates:raise RuntimeError('No supported shallow source patch; no map changes saved')
    _,hint,lo,hi=min(candidates,key=lambda v:v[0]);point=ground(hint)
    path=FOLDER+'/BP_JYU_AuthoredSpring'
    bp=unreal.load_asset(path)
    if bp and str(assets.get_metadata_tag(bp,'JYUOwner'))!=OWNER:raise RuntimeError('Foreign Blueprint at owned target')
    if not bp:
        factory=unreal.BlueprintFactory();factory.set_editor_property('parent_class',unreal.EcoVegetationHabitat)
        bp=unreal.AssetToolsHelpers.get_asset_tools().create_asset('BP_JYU_AuthoredSpring',FOLDER,unreal.Blueprint,factory)
        if not bp:raise RuntimeError('Spring BP creation failed')
        cdo=unreal.get_default_object(bp.generated_class())
        for k,v in {'plant':1,'drainage':.2,'shade':.25,'connected_fresh_water':True,'max_supply_rise_cm':120.}.items():cdo.set_editor_property(k,v)
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        assets.set_metadata_tag(bp,'JYUOwner',OWNER)
        if not assets.save_loaded_asset(bp,only_if_is_dirty=False):raise RuntimeError('Spring BP save failed')
    spring=actors.spawn_actor_from_class(assets.load_blueprint_class(path),point)
    spring.set_actor_label(label);spring.set_editor_property('tags',[OWNER]);spring.set_editor_property('is_spatially_loaded',False)
    spring.set_editor_property('region_id','Forest');spring.set_editor_property('water_surface_z',lo+12)
    spring.get_editor_property('bounds').set_box_extent(unreal.Vector(600,600,300),False)
    spring.set_editor_property('water_surface_size_cm',unreal.Vector2D(800,800))
    report['hydraulic_head_z']=lo+12;report['surveyed_max_depth_cm']=12;report['surveyed_bank_rise_cm']=hi-(lo+12)
if not spring.is_valid_habitat():raise RuntimeError('New source does not satisfy native authoring contract')
runtime.set_editor_property('enable_ecosystem_life',True)
if not levels.save_current_level():raise RuntimeError('Owned scene save failed')
report['life_enabled']=runtime.get_editor_property('enable_ecosystem_life')
report['spring_class']=spring.get_class().get_path_name();report['water_surface_z']=spring.get_editor_property('water_surface_z')
report['habitats']=len([a for a in actors.get_all_level_actors() if isinstance(a,unreal.EcoVegetationHabitat)])
(out/'Authoring.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('ECOSYSTEM_LIFE_AUTHORING_FINISHED')

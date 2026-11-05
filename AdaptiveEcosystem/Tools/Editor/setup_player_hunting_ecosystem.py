"""Author only the user's existing level and owned hunting assets. Idempotent and terrain-checked."""
import json, shutil
from pathlib import Path
import unreal as u
MAP='/Game/JWJ/1102_Integration_JWJ'
OWNER='JWJ.HuntingLoop.20261105'
ROOT='/Game/JWJ/Gameplay'
assets=u.EditorAssetLibrary
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
if not assets.does_asset_exist(MAP) or not levels.load_level(MAP):raise RuntimeError('Existing current level required')
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
if not world.get_path_name().startswith(MAP+'.'):raise RuntimeError('Unexpected current level')
if not u.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Terrain streaming failed')
all_actors=actors.get_all_level_actors()
runtimes=[a for a in all_actors if isinstance(a,u.EcoCreatureIntegrationSpawner)]
if len(runtimes)!=1:raise RuntimeError('Exactly one existing runtime required')
runtime=runtimes[0]
source=next(a for a in all_actors if isinstance(a,u.EcologyRegion) and str(a.region_id)=='JWJ_WildlifeTest')
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'PlayerHunting_20261105'
out.mkdir(parents=True,exist_ok=True)

def ground(point):
    result=u.EcoCreatureAnimationBuilder.project_placement_point(world,point)
    if isinstance(result,tuple):result=next((v for v in result if isinstance(v,u.Vector)),None)
    if not isinstance(result,u.Vector):raise RuntimeError('No traversable ground at '+str(point))
    return result

def owned(label,cls,point):
    actor=next((a for a in actors.get_all_level_actors() if a.get_actor_label()==label),None)
    if actor and OWNER not in [str(t) for t in actor.tags]:raise RuntimeError('Foreign actor label '+label)
    if not actor:
        actor=actors.spawn_actor_from_class(cls,point)
        actor.set_actor_label(label);actor.set_editor_property('tags',[OWNER]);actor.set_editor_property('is_spatially_loaded',False)
    return actor

# Survey both stages and the connecting corridor before changing the level.
center=source.get_actor_location()
destination=ground(center+u.Vector(15000,0,0))
route_points=[ground(center+u.Vector(x,0,0)) for x in range(4000,11001,500)]
for a,b in zip(route_points,route_points[1:]):
    if abs(a.z-b.z)>150:raise RuntimeError('Route ground step too steep')
for dx in [-5000,0,5000]:
    for dy in [-5000,0,5000]:ground(destination+u.Vector(dx,dy,0))

# Correct the attack bone to the moving right foot in MM_Attack_03. Keep existing montage timings.
data=assets.load_asset(ROOT+'/DA_EcoUnarmedCombo')
if not data:raise RuntimeError('Existing combo data required')
backup=out/'AssetBaseline';backup.mkdir(exist_ok=True)
asset_file=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))/'JWJ/Gameplay/DA_EcoUnarmedCombo.uasset'
if asset_file.exists() and not (backup/asset_file.name).exists():shutil.copy2(asset_file,backup/asset_file.name)
steps=list(data.get_editor_property('steps'))
if len(steps)!=3:raise RuntimeError('Expected existing three-step combo')
steps[2].set_editor_property('socket','foot_r')
data.modify();data.set_editor_property('steps',steps)
if not assets.save_loaded_asset(data,False):raise RuntimeError('Combo data save failed')

dest_id='JWJ_HuntingMeadow'
region=owned('JWJ_Hunting_MeadowRegion',u.EcologyRegion,destination)
region.set_editor_property('region_id',dest_id)
region.region_bounds.set_box_extent(u.Vector(6200,6200,2500),False)
region.set_editor_property('adjacent_region_ids',[source.region_id])
source.modify();source.set_editor_property('adjacent_region_ids',list(dict.fromkeys(list(source.adjacent_region_ids)+[u.Name(dest_id)])))
# Existing regional weather remains the producer. Use the same rainfall/temperature, different soil drainage.
region.set_editor_property('environment_state',source.get_editor_property('environment_state'))
route=owned('JWJ_Hunting_MeadowRoute',u.EcoHerdMigrationRoute,center)
for key,value in {'from_region':source.region_id,'to_region':dest_id,'points':route_points,'corridor_width':600.,'bidirectional':True,'shares_habitat_reports':True}.items():route.set_editor_property(key,value)
if not route.is_valid_route():raise RuntimeError('Authored route invalid')

groups=list(runtime.get_editor_property('groups'))
if not any(str(g.get_editor_property("region_id"))==dest_id for g in groups):
    group=u.EcoCreatureSpawnGroup();group.set_editor_property('region_id',dest_id)
    group.set_editor_property('herbivores',8);group.set_editor_property('wolves',1)
    group.set_editor_property('use_food_patch_position',True);group.set_editor_property('food_patch_position',destination)
    groups.append(group)

field_path=ROOT+'/BP_JWJ_HuntingVegetation'
field=assets.load_asset(field_path)
if not field:
    factory=u.BlueprintFactory();factory.set_editor_property('parent_class',u.EcoVegetationField)
    field=u.AssetToolsHelpers.get_asset_tools().create_asset('BP_JWJ_HuntingVegetation',ROOT,u.Blueprint,factory)
    assets.set_metadata_tag(field,'Owner',OWNER)
if str(assets.get_metadata_tag(field,'Owner'))!=OWNER:raise RuntimeError('Foreign field Blueprint')
cdo=u.get_default_object(field.generated_class())
# Reuse the established grass material and a present plant mesh; logic does not depend on art.
for path in ['/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassD','/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassA']:
    if assets.does_asset_exist(path):cdo.set_editor_property('patch_mesh',u.load_asset(path));break
material=assets.load_asset('/Game/JYU/Ecosystem/MI_JYU_EcosystemGrass')
if material:cdo.set_editor_property('patch_material',material)
u.BlueprintEditorLibrary.compile_blueprint(field)
if not assets.save_loaded_asset(field,False):raise RuntimeError('Vegetation class save failed')
for rid,point,drain,shade in [(str(source.region_id),center,.8,.1),(dest_id,destination,.2,.4)]:
    habitat=owned('JWJ_Hunting_Soil_'+rid,u.EcoVegetationHabitat,point)
    for key,value in {'region_id':rid,'plant':0,'drainage':drain,'shade':shade,'connected_fresh_water':False}.items():habitat.set_editor_property(key,value)
    habitat.get_editor_property("bounds").set_box_extent(u.Vector(6000,6000,5000),False)
    if not habitat.is_valid_habitat():raise RuntimeError('Habitat invalid')
runtime.modify()
for key,value in {'groups':groups,'enable_player_combat':True,'enable_vegetation':True,'vegetation_field_class':field.generated_class(),'enable_herd_journeys':True,'enable_waves':False}.items():runtime.set_editor_property(key,value)
if not any(isinstance(a,u.PlayerStart) for a in actors.get_all_level_actors()):
    owned('JWJ_Hunting_PlayerStart',u.PlayerStart,ground(center+u.Vector(0,-1000,0))+u.Vector(0,0,110))
if not levels.save_current_level():raise RuntimeError('Current level save failed')
report=dict(map=MAP,source=str(source.region_id),destination=dest_id,destination_ground=[destination.x,destination.y,destination.z],route_points=[[p.x,p.y,p.z] for p in route_points],
            life=runtime.get_editor_property('enable_ecosystem_life'),vegetation=True,journeys=True,waves=False,kick_bone='foot_r',
            source_population_preserved=True,authored_destination_deer=8,authored_destination_wolves=1,
            native_population_overrides='Active Native configuration determines actual counts; inspect authority snapshot',soil_only_no_invented_water=True)
(out/'CurrentLevelAuthoring.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
u.log('PLAYER_HUNTING_CURRENT_LEVEL_SAVED '+json.dumps(report))

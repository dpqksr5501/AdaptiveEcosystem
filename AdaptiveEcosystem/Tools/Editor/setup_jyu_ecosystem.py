"""Create a NEW owned playable ecosystem map + functional BP authoring assets.
Never regenerates an existing target map or saves the source/team maps.
"""
import json
from pathlib import Path
import unreal

SOURCE='/Game/JYU/Maps/LV_JYU_HerdMigration'
TARGET='/Game/JYU/Maps/LV_JYU_Ecosystem'
FOLDER='/Game/JYU/Ecosystem'
OWNER='JYU.Ecosystem.SoilV1.20261023'
assets=unreal.EditorAssetLibrary
tools=unreal.AssetToolsHelpers.get_asset_tools()
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'Vegetation_20261023'
out.mkdir(parents=True,exist_ok=True)
if assets.does_asset_exist(TARGET):raise RuntimeError('Existing target map refused; inspect manual work before changing it')
report={'source':SOURCE,'target':TARGET,'assets':[],'habitats':[],'weather':[],'removed_visual_weather':[]}

def owned_asset(path,create):
    if assets.does_asset_exist(path):
        a=unreal.load_asset(path)
        if assets.get_metadata_tag(a,'JYUOwner')!=OWNER:raise RuntimeError('Unowned asset refused '+path)
        return a
    a=create()
    if not a:raise RuntimeError('Asset creation failed '+path)
    assets.set_metadata_tag(a,'JYUOwner',OWNER)
    return a
def save(a):
    if not assets.save_loaded_asset(a,only_if_is_dirty=False):raise RuntimeError('Asset save failed '+a.get_path_name())
    report['assets'].append(a.get_path_name())
def bp(name,parent,defaults):
    path=FOLDER+'/'+name
    def create():
        factory=unreal.BlueprintFactory();factory.set_editor_property('parent_class',parent)
        return tools.create_asset(name,FOLDER,unreal.Blueprint,factory)
    asset=owned_asset(path,create)
    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    cls=assets.load_blueprint_class(path)
    if not cls:raise RuntimeError('No generated BP class '+path)
    default=unreal.get_default_object(cls)
    for key,value in defaults.items():default.set_editor_property(key,value)
    unreal.BlueprintEditorLibrary.compile_blueprint(asset);save(asset)
    return cls

# Preserve the complete existing grass opacity/normal/wind graph and texture
# parameters; add only per-instance, server-supplied moisture/stress tint.
mat_path=FOLDER+'/M_JYU_EcosystemGrass'
source_mat='/Game/MWLandscapeAutoMaterial/Materials/MASTER/MTL_MWAM_CoverFoliage_MASTER'
mat=owned_asset(mat_path,lambda:assets.duplicate_asset(source_mat,mat_path))
lib=unreal.MaterialEditingLibrary
base=lib.get_material_property_input_node(mat,unreal.MaterialProperty.MP_BASE_COLOR)
base_pin=lib.get_material_property_input_node_output_name(mat,unreal.MaterialProperty.MP_BASE_COLOR)
if not base:raise RuntimeError('Source material has no direct BaseColor; refuse to replace its opacity/attributes')
def node(kind,x,y,**props):
    n=lib.create_material_expression(mat,kind,x,y)
    for key,value in props.items():n.set_editor_property(key,value)
    return n
def connect(a,pin,b,target):
    inputs=[str(v) for v in lib.get_material_expression_input_names(b)]
    if target not in inputs:
        if len(inputs)!=1:raise RuntimeError('Unsupported material pins '+str(inputs)+' for '+target)
        target=inputs[0]
    if not lib.connect_material_expressions(a,pin,b,target):raise RuntimeError('Material connection failed '+target)
moisture=node(unreal.MaterialExpressionPerInstanceCustomData,1400,500,data_index=1,const_default_value=.5)
stress=node(unreal.MaterialExpressionPerInstanceCustomData,1400,700,data_index=2,const_default_value=0)
threshold=node(unreal.MaterialExpressionConstant,1400,300,r=.4)
subtract=node(unreal.MaterialExpressionSubtract,1600,400)
connect(threshold,'',subtract,'A');connect(moisture,'',subtract,'B')
amplify=node(unreal.MaterialExpressionMultiply,1800,400,const_b=2.5)
connect(subtract,'',amplify,'A')
sat=node(unreal.MaterialExpressionSaturate,2000,400);connect(amplify,'',sat,'Input')
maximum=node(unreal.MaterialExpressionMax,2200,450)
connect(sat,'',maximum,'A');connect(stress,'',maximum,'B')
interpolate=node(unreal.MaterialExpressionVertexInterpolator,2400,450);connect(maximum,'',interpolate,'VS')
green=node(unreal.MaterialExpressionConstant3Vector,2400,100,constant=unreal.LinearColor(.8,1.1,.65,1))
dry=node(unreal.MaterialExpressionConstant3Vector,2400,250,constant=unreal.LinearColor(1.5,.65,.22,1))
tint=node(unreal.MaterialExpressionLinearInterpolate,2600,200)
connect(green,'',tint,'A');connect(dry,'',tint,'B');connect(interpolate,'',tint,'Alpha')
result=node(unreal.MaterialExpressionMultiply,2850,100)
connect(base,base_pin,result,'A');connect(tint,'',result,'B')
if not lib.connect_material_property(result,'',unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('BaseColor hookup failed')
lib.recompile_material(mat);save(mat)
mi=owned_asset(FOLDER+'/MI_JYU_EcosystemGrass',lambda:assets.duplicate_asset('/Game/MWLandscapeAutoMaterial/Materials/Plants/MTL_MWAM_PlantsGrass',FOLDER+'/MI_JYU_EcosystemGrass'))
lib.set_material_instance_parent(mi,mat);lib.update_material_instance(mi);save(mi)

field=bp('BP_JYU_VegetationField',unreal.EcoVegetationField,{
    'patch_mesh':unreal.load_asset('/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassA'),
    'patch_material':mi,'patch_width_cm':280.,'patch_height_cm':60.})
weather=bp('BP_JYU_EcosystemWeather',unreal.EcoRegionEnvironmentAdapter,{
    'cycle_rainfall':True,'apply_authored_weather':False,'rain_cycle_seconds':180.,
    'rain_transition_fraction':.1,'dry_rainfall':0.,'wet_rainfall':.65})
habitat_types={
    'Grass':bp('BP_JYU_GrassHabitat',unreal.EcoVegetationHabitat,{'plant':0,'drainage':.6,'shade':.1,'connected_fresh_water':False}),
    'MoistSoil':bp('BP_JYU_MoistSoilHabitat',unreal.EcoVegetationHabitat,{'plant':0,'drainage':.2,'shade':.35,'connected_fresh_water':False}),
    'Shrub':bp('BP_JYU_ShrubHabitat',unreal.EcoVegetationHabitat,{'plant':2,'drainage':.6,'shade':.6,'connected_fresh_water':False})}
bp('BP_JYU_RiparianHabitat',unreal.EcoVegetationHabitat,{'plant':1,'drainage':.2,'shade':.25,'connected_fresh_water':False})

if not levels.new_level_from_template(TARGET,SOURCE):raise RuntimeError('Owned template copy failed')
world=editor.get_editor_world()
if not world.get_path_name().startswith(TARGET):raise RuntimeError('Source-map authoring refused')
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Partition load failed')
assets.set_metadata_tag(world,'JYUOwner',OWNER)
all_actors=actors.get_all_level_actors()
runtimes=[a for a in all_actors if isinstance(a,unreal.EcoCreatureIntegrationSpawner)]
if len(runtimes)!=1:raise RuntimeError('Expected one authority coordinator')
runtime=runtimes[0]
runtime.set_editor_property('enable_vegetation',True)
runtime.set_editor_property('vegetation_field_class',field)
runtime.set_editor_property('is_spatially_loaded',False)

# This copy uses the native received weather presentation. Remove only its old
# visual-only weather manager; the source map's actor/asset remains intact.
for actor in list(all_actors):
    if actor.get_class().get_name() in ('BP_WeatherManager_C','BP_WeatherManager_PlayerFollow_C'):
        report['removed_visual_weather'].append(actor.get_actor_label())
        actors.destroy_actor(actor)
for ordinal,group in enumerate(runtime.get_editor_property('groups')):
    region=str(group.get_editor_property('region_id'));center=group.get_editor_property('food_patch_position')
    w=actors.spawn_actor_from_class(weather,center+unreal.Vector(0,0,200))
    w.set_actor_label('JYU_Ecosystem_Weather_'+region);w.set_editor_property('region_ids',[region])
    w.set_editor_property('rain_phase_offset_seconds',ordinal*30.)
    w.set_editor_property('is_spatially_loaded',False);w.set_editor_property('tags',[OWNER])
    report['weather'].append(dict(region=region,offset=ordinal*30.,cycle=180))
    for kind,dx,dy,extent in (('Grass',-2400,-2200,unreal.Vector(1800,1800,5000)),
                              ('MoistSoil',2400,1800,unreal.Vector(1800,2600,5000)),
                              ('Shrub',-2400,2200,unreal.Vector(1800,1800,5000))):
        hint=center+unreal.Vector(dx,dy,0)
        point=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,hint)
        if isinstance(point,tuple):point=next((v for v in point if isinstance(v,unreal.Vector)),None)
        if not isinstance(point,unreal.Vector):raise RuntimeError('Habitat ground missing '+region+' '+kind)
        actor=actors.spawn_actor_from_class(habitat_types[kind],point)
        actor.set_actor_label('JYU_Ecosystem_'+region+'_'+kind);actor.set_editor_property('region_id',region)
        actor.get_editor_property('bounds').set_box_extent(extent,False)
        actor.set_editor_property('is_spatially_loaded',False);actor.set_editor_property('tags',[OWNER])
        report['habitats'].append(dict(region=region,kind=kind,position=[point.x,point.y,point.z],connected_water=False))
if not levels.save_current_level():raise RuntimeError('Owned ecosystem map save failed')
(out/'BPAuthoring.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('ECOSYSTEM_BP_AUTHORING_FINISHED '+TARGET)

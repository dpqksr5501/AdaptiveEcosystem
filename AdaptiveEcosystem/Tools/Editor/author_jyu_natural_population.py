"""Owned natural deer composition/growth authoring. No vendor or other map edits."""
import json,traceback
from pathlib import Path
import unreal
ROOT='/Game/JYU/Ecosystem/Natural'
OWNER='JYU.Ecosystem.NaturalHabitat.20261030'
a=unreal.EditorAssetLibrary;t=unreal.AssetToolsHelpers.get_asset_tools();m=unreal.MaterialEditingLibrary
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'NaturalPopulation_20261030'
out.mkdir(parents=True,exist_ok=True)
report={'assets':[]}
def load(path):
    v=unreal.load_asset(path)
    if not v:raise RuntimeError('Missing asset '+path)
    return v
def owned(name,create):
    path=ROOT+'/'+name
    if a.does_asset_exist(path):
        v=load(path)
        if a.get_metadata_tag(v,'JYUOwner')!=OWNER:raise RuntimeError('Unowned '+path)
    else:v=create(path,name)
    if not v:raise RuntimeError('Failed creation '+path)
    a.set_metadata_tag(v,'JYUOwner',OWNER)
    return v
def save(v):
    if not a.save_loaded_asset(v,only_if_is_dirty=False):raise RuntimeError('Save failed '+v.get_path_name())
    report['assets'].append(v.get_path_name())
def duplicate(src,name):return owned(name,lambda path,n:a.duplicate_asset(src,path))
def connect(src,output,dst,pin):
    inputs=[str(v) for v in m.get_material_expression_input_names(dst)]
    if pin not in inputs and len(inputs)==1:pin=inputs[0]
    return m.connect_material_expressions(src,output,dst,pin)
def coat_material(v):
    if a.get_metadata_tag(v,'CoatSchema')=='1':return v
    original=m.get_material_property_input_node(v,unreal.MaterialProperty.MP_BASE_COLOR)
    output=m.get_material_property_input_node_output_name(v,unreal.MaterialProperty.MP_BASE_COLOR) if original else ''
    if not original:raise RuntimeError('Coat source has no supported base colour '+v.get_path_name())
    tone=m.create_material_expression(v,unreal.MaterialExpressionScalarParameter,0,500)
    tone.set_editor_property('parameter_name','EcoInheritedCoatTone');tone.set_editor_property('default_value',1.)
    tone.set_editor_property('use_custom_primitive_data',True);tone.set_editor_property('primitive_data_index',5)
    multiply=m.create_material_expression(v,unreal.MaterialExpressionMultiply,400,500)
    if not connect(original,output,multiply,'A') or not connect(tone,'',multiply,'B'):raise RuntimeError('Coat tint connection')
    if not m.connect_material_property(multiply,'',unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('Coat output')
    a.set_metadata_tag(v,'CoatSchema','1');m.recompile_material(v);save(v);return v
def growth_material(src,name):
    path=ROOT+'/'+name
    # Do not accumulate wrappers on repeated authoring runs.
    if a.does_asset_exist(path):
        v=load(path)
        if a.get_metadata_tag(v,'JYUOwner')!=OWNER:raise RuntimeError('Unowned material')
        if a.get_metadata_tag(v,'GrowthFadeSchema')=='2':return coat_material(v)
    v=duplicate(src,name)
    original=m.get_material_property_input_node(v,unreal.MaterialProperty.MP_OPACITY_MASK)
    output=m.get_material_property_input_node_output_name(v,unreal.MaterialProperty.MP_OPACITY_MASK) if original else ''
    v.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
    m.set_material_usage(v,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    scalar=m.create_material_expression(v,unreal.MaterialExpressionScalarParameter,0,0)
    scalar.set_editor_property('parameter_name','EcoMaturityFade');scalar.set_editor_property('default_value',1.)
    scalar.set_editor_property('use_custom_primitive_data',True);scalar.set_editor_property('primitive_data_index',3)
    call=m.create_material_expression(v,unreal.MaterialExpressionMaterialFunctionCall,200,0)
    if not call.set_material_function(load('/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA')):raise RuntimeError('Dither function rejected')
    inputs=[str(x) for x in m.get_material_expression_input_names(call)]
    alpha=next((x for x in inputs if 'alpha' in x.lower()),None)
    if not alpha or not connect(scalar,'',call,alpha):raise RuntimeError('Dither inputs '+str(inputs))
    inverse=m.create_material_expression(v,unreal.MaterialExpressionOneMinus,300,0)
    if not connect(call,'',inverse,'Input'):raise RuntimeError('Inverse dither')
    select=m.create_material_expression(v,unreal.MaterialExpressionLinearInterpolate,400,0)
    reverse=m.create_material_expression(v,unreal.MaterialExpressionScalarParameter,0,150)
    reverse.set_editor_property('parameter_name','EcoImmatureSurface');reverse.set_editor_property('default_value',0.)
    reverse.set_editor_property('use_custom_primitive_data',True);reverse.set_editor_property('primitive_data_index',4)
    if not all((connect(call,'',select,'A'),connect(inverse,'',select,'B'),connect(reverse,'',select,'Alpha'))):raise RuntimeError('Complementary fade')
    final=select
    if original:
        final=m.create_material_expression(v,unreal.MaterialExpressionMultiply,400,0)
        if not connect(original,output,final,'A') or not connect(select,'',final,'B'):raise RuntimeError('Original mask not preserved')
    if not m.connect_material_property(final,'',unreal.MaterialProperty.MP_OPACITY_MASK):raise RuntimeError('Opacity output failed')
    m.recompile_material(v);a.set_metadata_tag(v,'GrowthFadeSchema','2');save(v);return coat_material(v)

def main():
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level('/Game/JYU/Maps/LV_JYU_Ecosystem'):raise RuntimeError('Owned map missing')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Terrain unavailable')
    runtime=next(x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(x,unreal.EcoCreatureIntegrationSpawner))
    bp=load(ROOT+'/BP_EcoNaturalDeer');unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    default=unreal.get_default_object(unreal.load_class(None,bp.get_path_name()+'_C'))
    variants=list(default.get_editor_property('appearance_variants'))
    for index,name in ((1,'Stag'),(2,'Doe')):
        variant=variants[index];mesh=variant.get_editor_property('mesh')
        profile=duplicate('/Game/JYU/Animation/DA_JYU_Deer_Animation','DA_EcoNaturalStag') if index==1 else load(ROOT+'/DA_EcoNaturalDoe')
        bones=[str(v) for v in unreal.EcoCreatureAnimationBuilder.get_skeletal_bone_names(mesh)]
        profile.set_editor_property('morph_bone',next(v for v in bones if v.lower().endswith('head')))
        profile.set_editor_property('morph_scale',unreal.Vector(1.12,1.12,1.12));profile.set_editor_property('age_driven_morph',True);save(profile)
        factory=unreal.AnimBlueprintFactory();factory.set_editor_property('parent_class',unreal.EcoCreatureAnimInstance);factory.set_editor_property('target_skeleton',mesh.get_editor_property('skeleton'))
        abp=owned('ABP_EcoNatural'+name,lambda path,n:t.create_asset(n,ROOT,unreal.AnimBlueprint,factory))
        if not unreal.EcoCreatureAnimationBuilder.build_pose_graph(abp,profile):raise RuntimeError('Growth pose graph failed '+name)
        save(abp)
        materials=[growth_material(slot.material_interface.get_path_name(),'M_EcoGrowth'+name+str(i)) for i,slot in enumerate(mesh.materials)]
        variant.set_editor_property('profile',profile);variant.set_editor_property('animation_class',unreal.load_class(None,abp.get_path_name()+'_C'))
        variant.set_editor_property('mesh_scale',unreal.Vector(1,1,1));variant.set_editor_property('growth_materials',materials)
        variants[index]=variant
    default.set_editor_property('appearance_variants',variants);default.set_editor_property('continuous_growth_appearance',True)
    default.set_editor_property('use_footstep_notifies',False)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp);save(bp)
    for name in ('TemperateMosaic','Dryland','Alpine'):
        profile=load(ROOT+'/DA_JYU_Habitat_'+name)
        guilds=list(profile.get_editor_property('guilds'))
        for guild,seconds in zip(guilds,(60.,120.,300.)):guild.set_editor_property('maturation_seconds',seconds)
        profile.set_editor_property('guilds',guilds);save(profile)
    report['survey']=json.loads(runtime.capture_habitat_authoring_report())
    if not levels.save_current_level():raise RuntimeError('Map save failed')
    report['result']='FINISHED'
try:main()
except Exception as error:
    report['result']='FAILED';report['error']=repr(error);unreal.log_error(traceback.format_exc())
finally:
    (out/'PopulationAuthoring.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.SystemLibrary.quit_editor()

"""Owned-map presentation authoring. Reuses real deer assets and common profile inputs.
Never edits vendor meshes/animations/materials or original team maps.
"""
import json,traceback
from pathlib import Path
import unreal

FOLDER='/Game/JYU/Ecosystem/Natural'
TARGET='/Game/JYU/Maps/LV_JYU_Ecosystem'
OWNER='JYU.Ecosystem.NaturalHabitat.20261030'
assets=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'NaturalHabitat_20261030'
out.mkdir(parents=True,exist_ok=True)
report={'assets':[],'variants':[],'lights':[]}

def owned(name,create):
    path=FOLDER+'/'+name
    if assets.does_asset_exist(path):
        a=unreal.load_asset(path)
        if assets.get_metadata_tag(a,'JYUOwner')!=OWNER:raise RuntimeError('Unowned asset '+path)
    else:a=create(path,name)
    if not a:raise RuntimeError('Creation failed '+path)
    assets.set_metadata_tag(a,'JYUOwner',OWNER)
    return a
def save(a):
    if not assets.save_loaded_asset(a,only_if_is_dirty=False):raise RuntimeError('Save failed '+a.get_path_name())
    report['assets'].append(a.get_path_name())
def tags(actor,*extra):actor.set_editor_property('tags',list(dict.fromkeys([str(t) for t in actor.tags]+list(extra))))
def duplicate(source,name):return owned(name,lambda path,n:assets.duplicate_asset(source,path))
def load(path):
    a=unreal.load_asset(path)
    if not a:raise RuntimeError('Missing source '+path)
    return a

def material(name,kind):
    m=owned(name,lambda path,n:tools.create_asset(n,FOLDER,unreal.Material,unreal.MaterialFactoryNew()))
    lib=unreal.MaterialEditingLibrary;lib.delete_all_material_expressions(m)
    m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property('two_sided',True)
    if kind in ('rain','snow'):
        # Renderer usage must be cooked explicitly; editor auto-usage is insufficient.
        lib.set_material_usage(m,unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES)
        lib.set_material_usage(m,unreal.MaterialUsage.MATUSAGE_NIAGARA_MESH_PARTICLES)
    m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT if kind in ('rain','snow') else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    if kind=='ground':m.set_editor_property('material_domain',unreal.MaterialDomain.MD_DEFERRED_DECAL)
    def node(cls,**props):
        a=lib.create_material_expression(m,cls,0,0)
        for k,v in props.items():a.set_editor_property(k,v)
        return a
    def connect(a,b,pin='Input',output=''):
        inputs=[str(v) for v in lib.get_material_expression_input_names(b)]
        if pin not in inputs and len(inputs)==1:pin=inputs[0]
        if pin not in inputs:
            candidates=[p for p in inputs if pin.lower().replace(' ','') in p.lower().replace(' ','')]
            if len(candidates)==1:pin=candidates[0]
        if not lib.connect_material_expressions(a,output,b,pin):raise RuntimeError('Material connection '+str(pin)+' in '+str(inputs)+' to '+b.get_class().get_name())
    def output(a,p):
        if not lib.connect_material_property(a,'',p):raise RuntimeError('Material output '+str(p))
    def constant(v):return node(unreal.MaterialExpressionConstant,r=v)
    def multiply(a,b=None,value=1):
        n=node(unreal.MaterialExpressionMultiply,const_b=value);connect(a,n,'A')
        if b:connect(b,n,'B')
        return n
    def subtract(a,value):
        n=node(unreal.MaterialExpressionSubtract,const_b=value);connect(a,n,'A');return n
    def saturate(a):n=node(unreal.MaterialExpressionSaturate);connect(a,n);return n
    def inverse(a):n=node(unreal.MaterialExpressionOneMinus);connect(a,n);return n
    uv=node(unreal.MaterialExpressionTextureCoordinate)
    x=node(unreal.MaterialExpressionComponentMask,r=True,g=False,b=False,a=False);connect(uv,x)
    y=node(unreal.MaterialExpressionComponentMask,r=False,g=True,b=False,a=False);connect(uv,y)
    ax=node(unreal.MaterialExpressionAbs);connect(subtract(x,.5),ax)
    ay=node(unreal.MaterialExpressionAbs);connect(subtract(y,.5),ay)
    if kind in ('rain','snow'):
        narrow=saturate(inverse(multiply(ax,value=45 if kind=='rain' else 8)))
        ends=saturate(inverse(multiply(ay,value=2 if kind=='rain' else 8)))
        depth=node(unreal.MaterialExpressionPixelDepth)
        camera_fade=saturate(multiply(subtract(depth,120),value=1/180))
        alpha=multiply(multiply(narrow,ends),camera_fade)
        output(multiply(alpha,value=.30 if kind=='rain' else .45),unreal.MaterialProperty.MP_OPACITY)
        color=node(unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(.11,.14,.17,1) if kind=='rain' else unreal.LinearColor(.18,.19,.21,1))
        output(color,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    elif kind=='water':
        color=node(unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(.025,.075,.065,1));output(color,unreal.MaterialProperty.MP_BASE_COLOR)
        fade=node(unreal.MaterialExpressionDepthFade,fade_distance_default=70.)
        vertex=node(unreal.MaterialExpressionVertexColor)
        edge=node(unreal.MaterialExpressionMultiply,const_b=1.);connect(vertex,edge,'A',output='A')
        output(multiply(multiply(fade,edge),value=.85),unreal.MaterialProperty.MP_OPACITY)
        output(constant(.18),unreal.MaterialProperty.MP_ROUGHNESS);output(constant(.5),unreal.MaterialProperty.MP_SPECULAR)
        time=node(unreal.MaterialExpressionTime)
        pan=node(unreal.MaterialExpressionPanner,speed_x=.025,speed_y=.013);connect(uv,pan,'Coordinate');connect(time,pan,'Time')
        noise=node(unreal.MaterialExpressionNoise,scale=5.,quality=1,levels=2)
        pos=node(unreal.MaterialExpressionAppendVector);connect(pan,pos,'A');connect(constant(0),pos,'B');connect(pos,noise,'Position')
        bump=node(unreal.MaterialExpressionDeriveNormalZ)
        nx=multiply(subtract(noise,.5),value=.12)
        append=node(unreal.MaterialExpressionAppendVector);connect(nx,append,'A');connect(nx,append,'B');connect(append,bump,'InXY')
        output(bump,unreal.MaterialProperty.MP_NORMAL)
    else:
        tint=node(unreal.MaterialExpressionVectorParameter,parameter_name='BiomeTint',default_value=unreal.LinearColor(.2,.25,.1,1));output(tint,unreal.MaterialProperty.MP_BASE_COLOR)
        world=node(unreal.MaterialExpressionWorldPosition)
        noise=node(unreal.MaterialExpressionNoise,scale=.002,quality=1,levels=2);connect(world,noise,'Position')
        sx=multiply(ax,ax);sy=multiply(ay,ay);radius=node(unreal.MaterialExpressionAdd);connect(sx,radius,'A');connect(sy,radius,'B')
        edge=saturate(inverse(multiply(radius,value=3.5)))
        strength=node(unreal.MaterialExpressionScalarParameter,parameter_name='BlendStrength',default_value=.35)
        output(multiply(multiply(edge,noise),strength),unreal.MaterialProperty.MP_OPACITY)
        output(constant(.9),unreal.MaterialProperty.MP_ROUGHNESS)
    lib.recompile_material(m);save(m);return m

def main():
    if not levels.load_level(TARGET):raise RuntimeError('Owned map missing')
    world=editor.get_editor_world()
    if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Terrain unavailable')
    all_actors=actors.get_all_level_actors()
    runtime=next(a for a in all_actors if isinstance(a,unreal.EcoCreatureIntegrationSpawner))
    rain_mat=material('M_EcoNaturalRain','rain');snow_mat=material('M_EcoNaturalSnow','snow')
    water_mat=material('M_EcoNaturalWater','water');ground_mat=material('M_EcoNaturalGround','ground')
    # Preserve the original landscape graph/physical outputs in a new owned MI.
    # Its legacy height-only water shading drew a flat blue patch without a water body.
    terrain=duplicate('/Game/Audio/Footsteps/Surfaces/MI_EcoLandscapeFootsteps','MI_EcoNaturalTerrain')
    lib=unreal.MaterialEditingLibrary
    for key,value in {'MW_WaterMaxWorldPosition':-100000.,'MW_WaterEdgeContrast':1.5,'MW_VariationWorldUVSize':950.,
        'MW_LandscapeWorldUVSizeFar':9000.,'MW_VariationNormalIntensity':.15,'MW_DirtSpecular':.2,'MW_StonesSpecular':.2,'MW_SnowMaskPower':3.}.items():
        lib.set_material_instance_scalar_parameter_value(terrain,key,value)
    lib.set_material_instance_vector_parameter_value(terrain,'MW_GrassColorCorrection',unreal.LinearColor(.72,.8,.6,1))
    lib.set_material_instance_vector_parameter_value(terrain,'MW_DirtColorCorrection',unreal.LinearColor(1.4,1.4,1.4,1))
    lib.update_material_instance(terrain);save(terrain)
    if not unreal.EcoCreatureAnimationBuilder.set_copied_landscape_material(world,terrain):raise RuntimeError('Owned landscape override failed')
    report['terrain_override']=dict(asset=terrain.get_path_name(),automatic_height_water=False,original_material_preserved=True)
    rain=duplicate('/Game/SHC/ART/FX/Rain_System','NS_EcoNaturalRain')
    snow=duplicate('/Game/SHC/ART/FX/NiagaraSnowfall/Effects/NS_Blizzard','NS_EcoNaturalSnow')
    for system,mat in ((rain,rain_mat),(snow,snow_mat)):
        if not unreal.EcoCreatureAnimationBuilder.configure_natural_precipitation(system,mat):raise RuntimeError('Owned precipitation renderer rejected')
        save(system)
    for name,tint,strength in (('TemperateMosaic',(.17,.23,.08),.25),('Dryland',(.34,.25,.13),.7),('Alpine',(.29,.31,.29),.65)):
        p=load(FOLDER+'/DA_JYU_Habitat_'+name)
        p.set_editor_property('ground_transition_material',ground_mat);p.set_editor_property('ground_tint',unreal.LinearColor(*tint,1))
        p.set_editor_property('ground_tint_strength',strength);p.set_editor_property('rain_visual',rain);p.set_editor_property('snow_visual',snow)
        p.set_editor_property('drive_day_night_lighting',name=='TemperateMosaic');save(p)
        p.set_editor_property('moon_sun_fraction',.015);p.set_editor_property('night_exposure_bias',-.9);save(p)
    mesh=owned('SM_EcoNaturalPool',lambda path,n:unreal.EcoCreatureAnimationBuilder.create_natural_pool_mesh(path,1907));save(mesh)
    for a in all_actors:
        if isinstance(a,unreal.EcoVegetationHabitat) and a.get_editor_property('connected_fresh_water'):
            point=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,a.get_actor_location())
            if isinstance(point,tuple):point=next((v for v in point if isinstance(v,unreal.Vector)),None)
            if not point:raise RuntimeError('Owned spring has no actual ground')
            # Explicit owned-scene authoring, not runtime inference from a water mesh.
            a.set_editor_property('water_surface_z',point.z+25.)
            a.set_editor_property('water_mesh',mesh);a.set_editor_property('water_material',water_mat)
            # Refresh supported component presentation from the same authored water height.
            a.set_actor_location(a.get_actor_location(),False,False)
    lights=sorted([a for a in all_actors if isinstance(a,unreal.DirectionalLight)],key=lambda a:-a.get_component_by_class(unreal.DirectionalLightComponent).get_editor_property('intensity'))
    for a,tag in zip(lights,['Eco.Sun','Eco.Moon']):tags(a,tag);report['lights'].append(dict(actor=a.get_actor_label(),tag=tag))
    for a in all_actors:
        if isinstance(a,unreal.SkyLight):tags(a,'Eco.Sky')
    exposure=next((a for a in all_actors if isinstance(a,unreal.PostProcessVolume) and a.get_editor_property('unbound')),None)
    if not exposure:
        exposure=actors.spawn_actor_from_class(unreal.PostProcessVolume,unreal.Vector());exposure.set_editor_property('unbound',True);exposure.set_actor_label('JYU_NaturalExposure')
    tags(exposure,'Eco.Exposure');exposure.set_editor_property('is_spatially_loaded',False)
    configure_deer(runtime)
    report['authoring_survey']=json.loads(runtime.capture_habitat_authoring_report())
    report['water_geometry']=[];report['water_like_components']=[]
    report['plane_components']=[]
    report['landscape_materials']=[];seen_materials=set()
    for a in all_actors:
        if isinstance(a,unreal.LandscapeProxy):
            landscape_material=a.get_editor_property('landscape_material')
            if landscape_material and landscape_material.get_path_name() not in seen_materials:
                seen_materials.add(landscape_material.get_path_name())
                lib=unreal.MaterialEditingLibrary
                report['landscape_materials'].append(dict(path=landscape_material.get_path_name(),
                    scalars={str(k):lib.get_material_instance_scalar_parameter_value(landscape_material,k) for k in lib.get_scalar_parameter_names(landscape_material)} if isinstance(landscape_material,unreal.MaterialInstanceConstant) else {},
                    vectors={str(k):str(lib.get_material_instance_vector_parameter_value(landscape_material,k)) for k in lib.get_vector_parameter_names(landscape_material)} if isinstance(landscape_material,unreal.MaterialInstanceConstant) else {}))
        if isinstance(a,unreal.EcoVegetationHabitat) and a.get_editor_property('connected_fresh_water'):
            surface=a.get_editor_property('water_surface');point=surface.get_world_location()
            ground=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,point)
            if isinstance(ground,tuple):ground=next((v for v in ground if isinstance(v,unreal.Vector)),None)
            report['water_geometry'].append(dict(actor=a.get_actor_label(),position=[point.x,point.y,point.z],ground=[ground.x,ground.y,ground.z] if ground else None,
                mesh=str(surface.get_editor_property('static_mesh')),material=str(surface.get_material(0))))
        for component in a.get_components_by_class(unreal.StaticMeshComponent):
            materials=[str(component.get_material(i)) for i in range(component.get_num_materials())]
            static_mesh=component.get_editor_property('static_mesh')
            if static_mesh and 'plane' in static_mesh.get_name().lower():
                p=component.get_world_location();report['plane_components'].append(dict(actor=a.get_actor_label(),mesh=static_mesh.get_path_name(),position=[p.x,p.y,p.z],materials=materials))
            if any('water' in m.lower() for m in materials):
                p=component.get_world_location();report['water_like_components'].append(dict(actor=a.get_actor_label(),component=component.get_name(),position=[p.x,p.y,p.z],materials=materials))
    if not levels.save_current_level():raise RuntimeError('Owned map save failed')
    report['result']='FINISHED'

def configure_deer(runtime):
    base=load('/Game/JYU/Animation/DA_JYU_Deer_Animation')
    doe_mesh=load('/Game/AnimalVarietyPack/DeerStagAndDoe/Meshes/SK_DeerDoe')
    skeleton=doe_mesh.get_editor_property('skeleton')
    bone_names=[str(v) for v in unreal.EcoCreatureAnimationBuilder.get_skeletal_bone_names(doe_mesh)]
    report['doe_bones']=bone_names
    folder='/Game/AnimalVarietyPack/DeerStagAndDoe/Animations/ANIM_DeerDoe_'
    clips=[load(folder+s) for s in ('IdleBreathe','Walk','WalkTurnL','WalkTurnR','Run')]
    factory=unreal.BlendSpaceFactoryNew();factory.set_editor_property('target_skeleton',skeleton)
    blend=owned('BS_EcoNaturalDoe',lambda path,n:tools.create_asset(n,FOLDER,unreal.BlendSpace,factory))
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_turning(blend,*clips,None,None,300.,900.):raise RuntimeError('Doe locomotion validation failed')
    save(blend)
    variants=[]
    for name,young in (('Doe',False),('Immature',True)):
        profile=duplicate(base.get_path_name(),'DA_EcoNatural'+name)
        profile.set_editor_property('locomotion',blend)
        poses=list(profile.get_editor_property('poses'))
        names=['IdleBreathe','IdleGraze','IdleLookAround','IdleRest','IdleLookAround','IdleSleep','GetHit','IdleRest','Death']
        for i,pose in enumerate(poses):pose.set_editor_property('clip',load(folder+names[i]))
        profile.set_editor_property('poses',poses)
        def bone(value):
            key=str(value)
            for candidate in (key,key.replace('Stag','Doe'),key.replace('DeerStag','DeerDoe'),key.replace('STAG_','DeerDoe_')):
                if candidate in bone_names:return candidate
            raise RuntimeError('Unmapped Doe bone '+key)
        for key in ('foot_bones','ik_end_bones'):profile.set_editor_property(key,[bone(v) for v in base.get_editor_property(key)])
        for key in ('body_bone','alert_head_bone'):profile.set_editor_property(key,bone(base.get_editor_property(key)))
        if young:
            head=next((n for n in bone_names if n.lower().endswith('head')),None)
            if not head:raise RuntimeError('Immature head bone missing')
            profile.set_editor_property('morph_bone',head);profile.set_editor_property('morph_scale',unreal.Vector(1.12,1.12,1.12))
        save(profile)
        af=unreal.AnimBlueprintFactory();af.set_editor_property('parent_class',unreal.EcoCreatureAnimInstance);af.set_editor_property('target_skeleton',skeleton)
        abp=owned('ABP_EcoNatural'+name,lambda path,n:tools.create_asset(n,FOLDER,unreal.AnimBlueprint,af))
        if not unreal.EcoCreatureAnimationBuilder.build_pose_graph(abp,profile):raise RuntimeError('Doe/immature pose graph rejected '+name)
        save(abp)
        cls=unreal.load_class(None,abp.get_path_name()+'_C')
        variants.append(unreal.EcoCreatureAppearanceVariant(mesh=doe_mesh,profile=profile,animation_class=cls,mesh_scale=unreal.Vector(.9,.9,1.05) if young else unreal.Vector(1,1,1)))
        report['variants'].append(dict(name=name,mesh=doe_mesh.get_path_name(),profile=profile.get_path_name(),animation=abp.get_path_name()))
    source=load('/Game/JYU/Creatures/BP_JYU_Deer');bp=duplicate(source.get_path_name(),'BP_EcoNaturalDeer')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    default=unreal.get_default_object(unreal.load_class(None,bp.get_path_name()+'_C'))
    adult=unreal.EcoCreatureAppearanceVariant(mesh=default.get_editor_property('visual_mesh'),profile=base,animation_class=default.get_editor_property('behavior_animation_class'),mesh_scale=unreal.Vector(1,1,1))
    default.set_editor_property('appearance_variants',[adult,adult,variants[0],variants[1]])
    # Doe clips have no authored contact notifies; use the supported speed/contact cadence for all morphs.
    default.set_editor_property('use_footstep_notifies',False)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp);save(bp)
    runtime.set_editor_property('herbivore_actor_class',unreal.load_class(None,bp.get_path_name()+'_C'))

try:main()
except Exception as error:
    report['result']='FAILED';report['error']=repr(error);unreal.log_error(traceback.format_exc())
finally:
    (out/'PresentationAuthoring.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('NATURAL_PRESENTATION_'+report['result'])
    unreal.SystemLibrary.quit_editor()

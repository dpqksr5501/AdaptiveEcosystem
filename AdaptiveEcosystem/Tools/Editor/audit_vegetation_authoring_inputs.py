"""Read only: inspect existing meshes/materials and the source owned map before authoring."""
import json
from pathlib import Path
import unreal
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'Vegetation_20261023'
out.mkdir(parents=True,exist_ok=True)
data={'meshes':[],'water_candidates':[],'groups':[]}
for suffix in ('A','B','C','D'):
    mesh=unreal.load_asset('/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_Grass'+suffix)
    if not mesh:continue
    bounds=mesh.get_bounding_box()
    materials=[]
    for entry in mesh.get_editor_property('static_materials'):
        m=entry.get_editor_property('material_interface')
        row={'path':m.get_path_name(),'class':m.get_class().get_name()}
        if isinstance(m,unreal.MaterialInstanceConstant):
            row['parent']=m.get_editor_property('parent').get_path_name()
            row['textures']=[dict(name=str(p),value=str(unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(m,p))) for p in unreal.MaterialEditingLibrary.get_texture_parameter_names(m)]
        materials.append(row)
    data['meshes'].append(dict(path=mesh.get_path_name(),bounds=str(bounds),materials=materials))
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not levels.load_level('/Game/JYU/Maps/LV_JYU_HerdMigration'):raise RuntimeError('Source owned map load failed')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Partition load failed')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for a in actors:
    label=a.get_actor_label()
    if any(word in (label+' '+a.get_class().get_name()).lower() for word in ('water','lake','river','pond')):
        origin,extent=a.get_actor_bounds(False)
        data['water_candidates'].append(dict(label=label,cls=a.get_class().get_name(),path=a.get_path_name(),location=str(a.get_actor_location()),bounds=[str(origin),str(extent)]))
    if isinstance(a,unreal.EcoCreatureIntegrationSpawner):
        for g in a.get_editor_property('groups'):
            data['groups'].append(dict(region=str(g.get_editor_property('region_id')),center=str(g.get_editor_property('food_patch_position'))))
(out/'AuthoringInputs.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('VEGETATION_AUTHORING_INPUTS_FINISHED')

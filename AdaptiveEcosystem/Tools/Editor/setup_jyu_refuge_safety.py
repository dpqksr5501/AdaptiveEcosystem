"""Create an owned refuge Blueprint and a new map from the current integration map.
Never saves the source map, original external actors, vendor assets or user audio edits.
"""
import hashlib
import json
from pathlib import Path
import unreal

SOURCE='/Game/JYU/Maps/LV_JYU_V3Integration'
TARGET='/Game/JYU/Maps/LV_JYU_RefugeSafety'
OWNER='JYU.RefugeSafety.v1'
ROOT='/Game/JYU/Environment'
saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'RefugeSafety_20261016'
repository=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
before=json.loads((saved/'UserAssetsBefore.json').read_text(encoding='utf-8'))
def check_preserved():
    changed=[a['path'] for a in before if hashlib.sha256((repository/a['path']).read_bytes()).hexdigest()!=a['sha256']]
    if changed:raise RuntimeError('Source/user assets changed: '+repr(changed))

assets=unreal.EditorAssetLibrary
tools=unreal.AssetToolsHelpers.get_asset_tools()
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
check_preserved()
def owned(path):
    obj=unreal.load_asset(path)
    if obj and str(assets.get_metadata_tag(obj,'JYUOwner'))!=OWNER:raise RuntimeError('Existing asset has another owner: '+path)
    return obj
def save(obj):
    assets.set_metadata_tag(obj,'JYUOwner',OWNER)
    if not assets.save_loaded_asset(obj,only_if_is_dirty=False):raise RuntimeError('Save failed '+obj.get_path_name())
def material(source,name):
    obj=owned(ROOT+'/'+name) or assets.duplicate_asset(source,ROOT+'/'+name)
    if not obj:raise RuntimeError(name)
    save(obj);return obj

grass=material('/Game/MWLandscapeAutoMaterial/Materials/Plants/MTL_MWAM_PlantsGrass','MI_JYU_RefugeBrush')
stone=material('/Game/MWLandscapeAutoMaterial/Materials/Cover/MTL_MWAM_CoverRocks','MI_JYU_RefugeStone')
bp=owned(ROOT+'/BP_JYU_ProtectedRefuge')
if not bp:
    factory=unreal.BlueprintFactory();factory.set_editor_property('parent_class',unreal.EcoRefugeHabitat)
    bp=tools.create_asset('BP_JYU_ProtectedRefuge',ROOT,unreal.Blueprint,factory)
if not bp:raise RuntimeError('Refuge Blueprint creation failed')
cdo=unreal.get_default_object(bp.generated_class())
cdo.set_editor_property('radius',1200)
cdo.set_editor_property('capacity',4)
cdo.set_editor_property('slot_radius_fraction',.55)
cdo.get_editor_property('brush').set_material(0,grass)
cdo.get_editor_property('boulders').set_material(0,stone)
save(bp)

if not assets.does_asset_exist(TARGET):
    # Engine template loading remaps World Partition external packages into the new map.
    if not levels.new_level_from_template(TARGET,SOURCE):raise RuntimeError('Map template copy failed')
else:
    if not levels.load_level(TARGET):raise RuntimeError('Open owned map failed')
world=editor.get_editor_world()
if not world.get_path_name().startswith(TARGET):raise RuntimeError('Refuse to author source level')
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Load copied World Partition cells failed')
check_preserved()
all_actors=list(actors.get_all_level_actors())
existing={a.get_actor_label():a for a in all_actors if isinstance(a,unreal.EcoRefugeHabitat)}
legacy=[a for a in all_actors if isinstance(a,unreal.EcoShelterAnchor) and not isinstance(a,unreal.EcoRefugeHabitat)
        and a.get_actor_label().startswith('JYU_Shelter_') and 800<=a.get_editor_property('radius')<=1800]
placements=[]
for index,old in enumerate(sorted(legacy,key=lambda a:a.get_actor_label())):
    label=old.get_actor_label().replace('JYU_Shelter_','JYU_ProtectedRefuge_')
    new=existing.get(label) or actors.spawn_actor_from_class(bp.generated_class(),old.get_actor_location(),old.get_actor_rotation())
    if not new:raise RuntimeError('Spawn failed '+label)
    new.set_actor_label(label)
    new.set_editor_property('radius',old.get_editor_property('radius'))
    new.set_editor_property('capacity',old.get_editor_property('capacity'))
    new.set_editor_property('slot_radius_fraction',.55)
    new.set_editor_property('layout_seed',1701+index)
    new.set_editor_property('brush_height',135 if 'Forest' in label else 115)
    new.set_editor_property('is_spatially_loaded',False)
    new.set_editor_property('tags',[OWNER])
    new.rebuild_habitat()
    placements.append({'label':label,'position':str(new.get_actor_location()),'radius':new.get_editor_property('radius'),
        'brush_instances':new.get_editor_property('brush').get_instance_count(),
        'boulder_instances':new.get_editor_property('boulders').get_instance_count()})
    actors.destroy_actor(old)
if not placements:
    placements=[{'label':a.get_actor_label(),'brush_instances':a.get_editor_property('brush').get_instance_count()} for a in existing.values()]
if len(placements)!=12:raise RuntimeError('Expected 12 authored refuges, got '+str(len(placements)))
runtime=[a for a in actors.get_all_level_actors() if isinstance(a,unreal.EcoCreatureIntegrationSpawner)]
if len(runtime)!=1:raise RuntimeError('Expected one common runtime')
runtime[0].set_editor_property('v3_use_authored_shelters',True)
if not levels.save_current_level():raise RuntimeError('Owned map save failed')
check_preserved()
(saved/'Authoring.json').write_text(json.dumps({'source':SOURCE,'target':TARGET,'blueprint':bp.get_path_name(),'placements':placements,
    'user_assets_preserved':len(before)},indent=2),encoding='utf-8')
unreal.log('JYU_REFUGE_AUTHORING_FINISHED '+str(len(placements)))

"""Owned PrimaryAssetLabel makes native runtime asset paths explicit cook dependencies."""
import json
from pathlib import Path
import unreal
folder='/Game/JYU/Ecosystem'
name='PAL_JYU_EcosystemRuntime'
path=folder+'/'+name
owner='JYU.Ecosystem.RuntimeDependencies.20261023'
assets=unreal.EditorAssetLibrary
label=assets.load_asset(path) if assets.does_asset_exist(path) else None
if label is not None and assets.get_metadata_tag(label,'EcosystemOwner')!=owner:raise RuntimeError('Existing label is not owned; preserved')
if label is None:
    factory=unreal.DataAssetFactory();factory.set_editor_property('data_asset_class',unreal.PrimaryAssetLabel)
    label=unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,folder,unreal.PrimaryAssetLabel,factory)
    if label is None:raise RuntimeError('PrimaryAssetLabel creation failed')
    assets.set_metadata_tag(label,'EcosystemOwner',owner)
paths=[
    '/Game/SHC/ART/FX/Rain_System','/Game/SHC/ART/FX/NiagaraSnowfall/Effects/NS_Blizzard',
    '/Game/SHC/Audio/Environment/A_Rain_Cue',
    *['/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_Grass'+letter for letter in 'ABCD'],
    '/Engine/BasicShapes/Cube','/Engine/BasicShapes/Plane','/Game/JYU/Materials/M_JYU_Surface_Water',
    '/Game/JYU/Ecosystem/MI_JYU_EcosystemGrass']
references=[]
for dependency in paths:
    asset=unreal.load_asset(dependency)
    if asset is None:raise RuntimeError('Missing real dependency '+dependency)
    references.append(asset)
rules=label.get_editor_property('rules')
rules.set_editor_property('cook_rule',unreal.PrimaryAssetCookRule.ALWAYS_COOK)
rules.set_editor_property('apply_recursively',True)
label.set_editor_property('rules',rules)
label.set_editor_property('label_assets_in_my_directory',False)
label.set_editor_property('is_runtime_label',False)
label.set_editor_property('explicit_assets',references)
if not assets.save_loaded_asset(label):raise RuntimeError('Runtime dependency label save failed')
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'EcosystemLife_20261023'
out.mkdir(parents=True,exist_ok=True)
(out/'RuntimeDependencies.json').write_text(json.dumps(dict(label=path,owner=owner,dependencies=paths,cook_rule=str(rules.get_editor_property('cook_rule')),passed=True),indent=2),encoding='utf-8')
unreal.log('ECOSYSTEM_RUNTIME_DEPENDENCIES_SAVED')

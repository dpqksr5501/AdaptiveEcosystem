"""Restore main's missing moved PlayerFollow class without changing existing maps.

Run in an idle editor session. Only the compatibility Blueprint may be created/saved;
main's weather graph, redirector, maps, and external actors remain untouched.
"""
import unreal

PARENT = '/Game/SHC/Blueprints/Weather/BP_WeatherManager'
TARGET = '/Game/SHC/Blueprints/Weather/BP_WeatherManager_PlayerFollow'
OWNER_TAG = 'JYUMainMergeCompatibility'
OWNER = '2026-10-22: missing moved PlayerFollow class; inherits current main weather behavior'

assets = unreal.EditorAssetLibrary
parent = assets.load_blueprint_class(PARENT)
if not parent:
    raise RuntimeError('Main weather parent did not load')

if assets.does_asset_exist(TARGET):
    asset = unreal.load_asset(TARGET)
    if not asset or str(assets.get_metadata_tag(asset, OWNER_TAG)) != OWNER:
        raise RuntimeError('Refuse to overwrite an asset owned by another author')
    existing_class = assets.load_blueprint_class(TARGET)
    if not existing_class or not unreal.MathLibrary.class_is_child_of(existing_class, parent):
        raise RuntimeError('Existing compatibility parent changed; review before authoring')
else:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', parent)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'BP_WeatherManager_PlayerFollow', '/Game/SHC/Blueprints/Weather', unreal.Blueprint, factory)
    if not asset:
        raise RuntimeError('Compatibility class creation failed')
    assets.set_metadata_tag(asset, OWNER_TAG, OWNER)
    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError('Compatibility class save failed')

# LoadBlueprintClass checks AssetRegistry type before resolving ObjectRedirector.
# Load the generated class directly to exercise the path serialized in old actors.
legacy = unreal.load_class(None, '/Game/Actors/BP_WeatherManager_PlayerFollow.BP_WeatherManager_PlayerFollow_C')
current = assets.load_blueprint_class(TARGET)
if not legacy or not current or legacy != current:
    raise RuntimeError('Legacy generated class did not resolve to the compatibility class')
unreal.log('JYU_MAIN_WEATHER_COMPATIBILITY_OK')

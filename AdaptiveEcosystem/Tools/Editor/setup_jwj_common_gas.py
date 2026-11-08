"""Configure the shared JWJ GAS player defaults in Unreal Editor Python.

Run with -run=pythonscript -script=<this file>. Saves only the named assets
and /Game/JWJ/1102_Integration_JWJ. Restart PIE after applying.
"""
import unreal as u


ROOT = "/Game/JWJ/Gameplay"
MAP = "/Game/JWJ/1102_Integration_JWJ"
assets = u.EditorAssetLibrary
tools = u.AssetToolsHelpers.get_asset_tools()


def duplicate(source, destination):
    asset = u.load_asset(destination)
    if asset is None:
        asset = assets.duplicate_asset(source, destination)
    if asset is None:
        raise RuntimeError("Cannot create " + destination)
    return asset


def defaults(blueprint):
    u.BlueprintEditorLibrary.compile_blueprint(blueprint)
    return u.get_default_object(u.BlueprintEditorLibrary.generated_class(blueprint))


def save(asset):
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Cannot save " + asset.get_path_name())


levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
if not levels.load_level(MAP):
    raise RuntimeError("Cannot load " + MAP)
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()

# Reuse the existing attack Input Action, movement mappings, Pawn and Controller.
attack = u.load_asset("/Game/Variant_Combat/Input/Actions/IA_ComboAttack")
if attack is None:
    raise RuntimeError("Existing attack Input Action is missing")
mapping = u.load_asset(ROOT + "/IMC_EcoAbilities_Common")
if mapping is None:
    factory = u.InputMappingContext_Factory()
    mapping = tools.create_asset("IMC_EcoAbilities_Common", ROOT,
                                 u.InputMappingContext, factory)
    if mapping is not None:
        attack_key = u.Key()
        attack_key.set_editor_property("key_name", "F")
        mapping.map_key(attack, attack_key)
if mapping is None:
    raise RuntimeError("Cannot create ability mapping context")
save(mapping)

input_config = u.load_asset(ROOT + "/DA_EcoAbilityInputs_Common")
if input_config is None:
    factory = u.DataAssetFactory()
    factory.set_editor_property("data_asset_class", u.EcoAbilityInputConfig)
    input_config = tools.create_asset("DA_EcoAbilityInputs_Common", ROOT,
                                     u.EcoAbilityInputConfig, factory)
    if input_config is None:
        raise RuntimeError("Cannot create ability input config")
    binding = u.EcoAbilityInputBinding()
    binding.set_editor_property("action", attack)
    binding.set_editor_property("ability", u.EcoGameplayAbility_MeleeStrike)
    input_config.set_editor_property("ability_inputs", [binding])
save(input_config)

pawn = duplicate("/Game/Common/Gameplay/BP_EcoPlayer_Common", ROOT + "/BP_EcoPlayer_Common")
pawn_defaults = defaults(pawn)
avatar = pawn_defaults.get_editor_property("ability_avatar")
pawn.modify()
pawn_defaults.modify()
avatar.modify()
avatar.set_editor_property("input_config", input_config)
avatar.set_editor_property("ability_inputs", [])
save(pawn)

controller = duplicate("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController",
                       ROOT + "/BP_EcoPlayerController_Common")
controller_defaults = defaults(controller)
contexts = list(controller_defaults.get_editor_property("default_mapping_contexts"))
if mapping not in contexts:
    contexts.append(mapping)
controller.modify()
controller_defaults.modify()
controller_defaults.set_editor_property("default_mapping_contexts", contexts)
save(controller)

mode = duplicate("/Game/Common/Gameplay/BP_EcoGameMode_Common", ROOT + "/BP_EcoGameMode_Common")
mode_defaults = defaults(mode)
mode.modify()
mode_defaults.modify()
mode_defaults.set_editor_property("player_state_class", u.EcoPlayerState)
mode_defaults.set_editor_property("default_pawn_class", u.BlueprintEditorLibrary.generated_class(pawn))
mode_defaults.set_editor_property("player_controller_class", u.BlueprintEditorLibrary.generated_class(controller))
save(mode)

settings = world.get_world_settings()
settings.modify()
settings.set_editor_property("default_game_mode", u.BlueprintEditorLibrary.generated_class(mode))
if not levels.save_current_level():
    raise RuntimeError("Cannot save JWJ level")
u.log("[JWJ GAS Setup] Saved shared GameMode, Pawn, Controller and F attack mapping in " + ROOT)

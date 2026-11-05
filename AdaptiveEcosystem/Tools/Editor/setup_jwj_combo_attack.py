"""Author the owned JWJ combo assets. Existing combo timing is preserved on rerun."""
import unreal as u
ROOT = "/Game/JWJ/Gameplay"
assets = u.EditorAssetLibrary
tools = u.AssetToolsHelpers.get_asset_tools()
montage = u.load_asset(ROOT + "/AM_EcoUnarmedCombo")
if montage is None:
    montage = assets.duplicate_asset("/Game/Variant_Combat/Anims/AM_ComboAttack", ROOT + "/AM_EcoUnarmedCombo")
    sequences = [u.load_asset("/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_0"+str(i)) for i in (1,2,3)]
    assert u.EcoComboAuthoringLibrary.configure_combo_montage(montage, sequences)
    assert assets.save_loaded_asset(montage, False)
    assert assets.save_loaded_asset(sequences[0].get_editor_property("skeleton"), False)
data = u.load_asset(ROOT + "/DA_EcoUnarmedCombo")
if data is None:
    factory = u.DataAssetFactory()
    factory.set_editor_property("data_asset_class", u.EcoComboAttackData)
    data = tools.create_asset("DA_EcoUnarmedCombo", ROOT, u.EcoComboAttackData, factory)
    steps = []
    for section, socket in [("LeftPunch","Attack_Hand_L"),("RightPunch","Attack_Hand_R"),("Kick","Attack_Foot")]:
        step = u.EcoComboStep()
        step.set_editor_property("section", section)
        step.set_editor_property("socket", socket)
        steps.append(step)
    data.set_editor_property("montage", montage)
    data.set_editor_property("steps", steps)
    assert assets.save_loaded_asset(data, False)
pawn = u.load_asset(ROOT + "/BP_EcoPlayer_Common")
u.BlueprintEditorLibrary.compile_blueprint(pawn)
cdo = u.get_default_object(u.BlueprintEditorLibrary.generated_class(pawn))
pawn.modify(); cdo.modify()
hit = cdo.get_editor_property("melee_hit")
hit.modify(); hit.set_editor_property("attack_data", data)
assert assets.save_loaded_asset(pawn, False)
config = u.load_asset(ROOT + "/DA_EcoAbilityInputs_Common")
bindings = list(config.get_editor_property("ability_inputs"))
attack = u.load_asset("/Game/Variant_Combat/Input/Actions/IA_ComboAttack")
for binding in bindings:
    if binding.get_editor_property("action") == attack:
        binding.set_editor_property("ability", u.EcoGameplayAbility_ComboAttack)
        binding.set_editor_property("activation_event", u.TriggerEvent.STARTED)
config.modify(); config.set_editor_property("ability_inputs", bindings)
assert assets.save_loaded_asset(config, False)
u.log("[EcoComboSetup] PASS saved Montage, sockets, combo data, Pawn and GAS binding")

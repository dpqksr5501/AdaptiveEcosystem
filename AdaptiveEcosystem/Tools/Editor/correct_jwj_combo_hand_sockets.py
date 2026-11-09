"""Correct the existing owned combo's hands only; preserve all other authored values."""
import json
from pathlib import Path
import unreal as u

path = '/Game/JWJ/Gameplay/DA_EcoUnarmedCombo'
data = u.load_asset(path)
if not data:
    raise RuntimeError('Existing combo data required')
steps = list(data.get_editor_property('steps'))
if len(steps) != 3 or [str(s.get_editor_property('section')) for s in steps] != ['LeftPunch', 'RightPunch', 'Kick']:
    raise RuntimeError('Unexpected combo layout; no asset changed')

def snapshot(asset):
    return dict(montage=str(asset.get_editor_property('montage')),
                steps=[dict(section=str(s.section), socket=str(s.socket), radius=s.radius, damage=s.damage)
                       for s in asset.get_editor_property('steps')])

before = snapshot(data)
data.modify()
steps[0].set_editor_property('socket', 'Attack_Hand_R')
steps[1].set_editor_property('socket', 'Attack_Hand_L')
data.set_editor_property('steps', steps)
after = snapshot(data)
assert before['montage'] == after['montage']
for index, (old, new) in enumerate(zip(before['steps'], after['steps'])):
    assert all(old[key] == new[key] for key in ['section', 'radius', 'damage'])
    if index == 2:
        assert old == new, 'Kick must remain unchanged'
if not u.EditorAssetLibrary.save_loaded_asset(data, False):
    raise RuntimeError('Combo data save failed')
out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / 'PlayerHunting_20261105'
(out / 'HandSocketCorrection.json').write_text(json.dumps(dict(result='PASS', before=before, after=after), indent=2), encoding='utf-8')
u.log('COMBO_HAND_SOCKET_CORRECTION_PASS')

"""팀 생태계 맵의 우리 소유 복사본을 만든다 (원본은 저장하지 않는다).

팀 도구(Tools/Editor/setup_jyu_ecosystem.py 등)와 같은 방식: LevelEditorSubsystem.new_level_from_template(대상, 원본)
— 원본을 이름 없는 새 패키지로 불러(템플릿) 대상 경로로 저장한다. 월드 파티션 외부 액터·외부 개체 파일도 대상 맵 이름 아래로 새로 저장된다.
대상이 이미 있으면 거절한다 (손으로 고친 것을 덮어쓰지 않는다).
그다음 맵 패키지에 출처 표식(메타데이터)만 더해 맵 파일 하나만 다시 저장한다 — 액터·레벨 설정은 바꾸지 않는다.

실행: UnrealEditor-Cmd.exe <uproject> -unattended -nop4 -nosplash -NullRHI -ExecutePythonScript=<이 파일> -CopyOut=<보고 json>
"""
import json
import os
import re

import unreal

SOURCE = '/Game/JYU/Maps/LV_JYU_Ecosystem'
TARGET = '/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem'

cmd = unreal.SystemLibrary.get_command_line()
m = re.search(r'-CopyOut=(\S+)', cmd)
OUT = m.group(1).strip('"') if m else None

assets = unreal.EditorAssetLibrary
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

rep = {'source': SOURCE, 'target': TARGET}
try:
    if not assets.does_asset_exist(SOURCE):
        raise RuntimeError('원본 맵이 없다 ' + SOURCE)
    if assets.does_asset_exist(TARGET):
        raise RuntimeError('대상 맵이 이미 있다 — 덮어쓰지 않는다 ' + TARGET)
    if not levels.new_level_from_template(TARGET, SOURCE):
        raise RuntimeError('템플릿 복사 실패')
    world = editor.get_editor_world()
    rep['world'] = world.get_path_name()
    if not rep['world'].startswith(TARGET + '.'):
        raise RuntimeError('복사 뒤 편집기 월드가 대상이 아니다 — 원본을 건드리지 않게 멈춘다 ' + rep['world'])
    lib = unreal.WorldPartitionBlueprintLibrary
    descs = lib.get_actor_descs()
    rep['actor_descs'] = len(descs)
    pkgs = sorted(str(d.get_editor_property('actor_package')) for d in descs)
    rep['desc_packages_outside_target'] = [p for p in pkgs if not p.startswith('/Game/__ExternalActors__/EcoTest/Maps/LV_EcoV3_JYUEcosystem/')][:20]
    # 출처 표식 (맵 패키지 메타데이터) — 팀 소유 표식 JYUOwner 는 복사된 그대로 둔다 (지우지 않는다)
    rep['metadata_before'] = {k: assets.get_metadata_tag(world, k) for k in ('JYUOwner', 'EcoV3Owner', 'EcoV3CopySource')}
    assets.set_metadata_tag(world, 'EcoV3Owner', 'EcoTest.JYUEcosystemCopy.20261025')
    assets.set_metadata_tag(world, 'EcoV3CopySource', SOURCE)
    pkg = world.get_outermost()
    if not unreal.EditorLoadingAndSavingUtils.save_packages([pkg], False):
        raise RuntimeError('맵 패키지 다시 저장 실패')
    rep['metadata_after'] = {k: assets.get_metadata_tag(world, k) for k in ('JYUOwner', 'EcoV3Owner', 'EcoV3CopySource')}
    rep['ok'] = True
    unreal.log('ECOV3_COPY_DONE ' + TARGET + ' descs=' + str(len(descs)))
except Exception as e:  # 보고만 하고 끝낸다
    rep['ok'] = False
    rep['error'] = str(e)
    unreal.log_error('ECOV3_COPY_FAILED ' + str(e))
if OUT:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
unreal.SystemLibrary.quit_editor()

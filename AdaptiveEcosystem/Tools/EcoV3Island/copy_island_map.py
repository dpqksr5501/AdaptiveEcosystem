"""팀 섬 맵의 우리 소유 복사본 /Game/EcoTest/Maps/LV_EcoV3_Island 를 만들고 생태 장치만 더한다 (원본은 저장하지 않는다).

설계: Docs/RL_Policy/ISLAND_STAGE.md 2절.

1. 대상이 없으면 LevelEditorSubsystem.new_level_from_template(대상, 원본) 으로 복사한다 (f46685d7 조연우 맵 복사와 같은 방식).
   원본을 이름 없는 새 패키지로 불러 대상 경로로 저장한다 — 월드 파티션 외부 액터·외부 개체도 대상 맵 이름 아래 새 파일이다.
   대상이 이미 있으면 복사하지 않고 그 맵을 연다 (손으로 고친 것을 덮어쓰지 않는다).
2. 복사본에만 더한다 (우리 꼬리표 EcoV3IslandCopy 가 붙은 액터만 만들거나 고친다 — 다른 액터는 건드리지 않는다):
   - AEcologyRegion Eco_Region_Island (지역 Island, 상자 = 섬 무대 정사각 2800 m)
   - AEcoCreatureIntegrationSpawner Eco_CreatureRuntime (통합 맵 조정자 값 + bUseV3Policy + bV3IslandStage)
   - PlayerStart Eco_PlayerStart_Island (고원 위)
   - 월드 설정 게임 모드 덮기 = EcoCreatureIntegrationGameMode
   - 맵 패키지 메타데이터 EcoV3Owner·EcoV3CopySource
3. 편집기 월드가 대상인지 확인한 뒤에만 저장한다 (save_current_level — 대상 맵과 대상 외부 액터 패키지).

실행 (창 없음):
  UnrealEditor-Cmd.exe <uproject> -unattended -nop4 -nosplash -NullRHI -NoSound -DisablePlugins=Bridge,Fab
      -ExecutePythonScript=<이 파일> -CopyOut=<보고 json>
"""
import json
import os
import re
import traceback

import unreal

SOURCE = '/Game/Map/LV_SHC_IslandEcosystem1_WP'
TARGET = '/Game/EcoTest/Maps/LV_EcoV3_Island'
TAG = 'EcoV3IslandCopy'
OWNER = 'EcoTest.IslandCopy.20261105'
ROOT = '/Game/Creatures/Integrated/'

# 섬 무대 정사각 (cm). 조사(ISLAND_STAGE.md 0.1): 땅 경계 x -903 ~ +1797 m, y -543 ~ +1527 m — 가운데 (447, 492) m, 긴 변 2700 m + 양쪽 50 m.
# 지역 상자 = 섬 무대 정사각. 섬 모드는 이 상자의 가로 반폭 큰 쪽으로 정사각 세계를 만든다 (EcoV3Island.h).
REGION_CENTER = (44700.0, 49200.0, 0.0)
REGION_EXTENT = (140000.0, 140000.0, 15000.0)
# 보는 자리·팀 그대로 판(통합 v3 를 켜지 못했을 때)의 시작 자리: 고원 위 첫 무리 자리 곁.
# 첫 무리 자리는 자동 고르기로 (379, 444) m (땅 지도 지문 1d7c3ff530e12d8a, 11-05 헤드리스) — 그 남서쪽 85 m 에서 북동쪽(자리)을 본다
VIEW_XY = (31900.0, 38400.0)

cmd = unreal.SystemLibrary.get_command_line()
m = re.search(r'-CopyOut=(\S+)', cmd)
OUT = m.group(1).strip('"') if m else None

assets = unreal.EditorAssetLibrary
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

rep = {'source': SOURCE, 'target': TARGET, 'steps': []}


def xyz(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def tags_of(a):
    return [str(t) for t in a.get_editor_property('tags')]


try:
    if not assets.does_asset_exist(SOURCE):
        raise RuntimeError('원본 맵이 없다 ' + SOURCE)
    if assets.does_asset_exist(TARGET):
        rep['steps'].append('대상이 이미 있다 — 복사하지 않고 연다')
        if not levels.load_level(TARGET):
            raise RuntimeError('대상 맵을 열지 못했다')
        rep['copied'] = False
    else:
        if not levels.new_level_from_template(TARGET, SOURCE):
            raise RuntimeError('템플릿 복사 실패')
        rep['steps'].append('템플릿 복사')
        rep['copied'] = True
    world = editor.get_editor_world()
    rep['world'] = world.get_path_name()
    if not rep['world'].startswith(TARGET + '.'):
        raise RuntimeError('편집기 월드가 대상이 아니다 — 원본을 건드리지 않게 멈춘다 ' + rep['world'])

    lib = unreal.WorldPartitionBlueprintLibrary
    descs = lib.get_actor_descs()
    rep['actor_descs_before'] = len(descs)
    ext_root = '/Game/__ExternalActors__/EcoTest/Maps/LV_EcoV3_Island/'
    pkgs = sorted(str(d.get_editor_property('actor_package')) for d in descs)
    rep['desc_packages_outside_target'] = [p for p in pkgs if not p.startswith(ext_root)][:20]
    if rep['desc_packages_outside_target']:
        raise RuntimeError('대상 밖 외부 액터 패키지가 있다 — 멈춘다')
    # 지면 검사를 하려고 모든 액터를 편집기 메모리에 부른다 (저장하지 않는다 — 더러워진 것만 아래에서 저장)
    guids = [d.get_editor_property('guid') for d in descs]
    rep['load_actors'] = bool(lib.load_actors([g for g in guids if g is not None]))

    all_actors = list(actors_sub.get_all_level_actors())
    rep['actors_loaded'] = len(all_actors)
    foreign = [a.get_actor_label() for a in all_actors
               if isinstance(a, (unreal.EcologyRegion, unreal.EcoCreatureIntegrationSpawner)) and TAG not in tags_of(a)]
    if foreign:
        raise RuntimeError('우리 꼬리표가 없는 생태 액터가 이미 있다 — 덮어쓰지 않는다: ' + ', '.join(foreign))

    def ground(x, y, z=0.0):
        r = unreal.EcoCreatureLevelLibrary.probe_ground(world, unreal.Vector(x, y, z))
        if not r.valid:
            return None
        return r.position

    def owned(label, cls, point, folder):
        matches = [a for a in all_actors if a.get_actor_label() == label]
        if matches:
            if len(matches) != 1 or TAG not in tags_of(matches[0]) or not isinstance(matches[0], cls):
                raise RuntimeError('우리 것이 아닌 같은 이름 액터: ' + label)
            actor = matches[0]
            actor.modify()
            actor.set_actor_location(point, False, False)
        else:
            actor = actors_sub.spawn_actor_from_class(cls, point)
            if not actor:
                raise RuntimeError('액터를 만들지 못했다: ' + label)
            actor.set_actor_label(label)
            actor.set_editor_property('tags', [unreal.Name(TAG)])
            all_actors.append(actor)
        # 논리 상태(지역·조정자)·시작점은 카메라 스트리밍과 무관하게 늘 불린다
        actor.set_editor_property('is_spatially_loaded', False)
        actor.set_folder_path('EcologyRuntime/' + folder)
        return actor

    view = ground(VIEW_XY[0], VIEW_XY[1])
    if view is None:
        raise RuntimeError('보는 자리 지면을 찾지 못했다 ' + str(VIEW_XY))
    rep['view_ground'] = xyz(view)
    # 팀 그대로 판(통합 v3 를 켜지 못한 경우)의 시작 자리: 보는 자리 둘레 3 m 간격 (사슴 8·늑대 1)
    deer_pts = []
    for i in range(16):
        if len(deer_pts) >= 8:
            break
        p = ground(VIEW_XY[0] + 600.0 + 300.0 * (i % 4), VIEW_XY[1] + 600.0 + 300.0 * (i // 4))
        if p is not None:
            deer_pts.append(p)
    wolf = ground(VIEW_XY[0] - 2500.0, VIEW_XY[1] - 2500.0)
    if len(deer_pts) < 8 or wolf is None:
        raise RuntimeError('팀 그대로 판 시작 자리를 다 찾지 못했다 (사슴 %d)' % len(deer_pts))

    deer_bp = unreal.load_class(None, ROOT + 'BP_EcoDeer.BP_EcoDeer_C')
    wolf_bp = unreal.load_class(None, ROOT + 'BP_EcoWolf.BP_EcoWolf_C')
    deer_config = unreal.load_asset(ROOT + 'DA_EcoDeer')
    wolf_config = unreal.load_asset(ROOT + 'DA_EcoWolf')
    footsteps = unreal.load_asset('/Game/Audio/Footsteps/Settings/DA_EcoFootsteps')
    if not all((deer_bp, wolf_bp, deer_config, wolf_config, footsteps)):
        raise RuntimeError('통합 맵 동물 에셋이 없다')

    center = unreal.Vector(*REGION_CENTER)
    with unreal.ScopedEditorTransaction('섬 무대 생태 장치 (EcoV3 섬 복사본)'):
        region = owned('Eco_Region_Island', unreal.EcologyRegion, center, 'Regions')
        region.region_bounds.set_box_extent(unreal.Vector(*REGION_EXTENT))
        region.set_editor_property('region_id', 'Island')
        region.set_editor_property('adjacent_region_ids', [])
        region.set_editor_property('arrival_offset', view - center)
        # 먹이 장부 = 통합 맵 Forest 와 같다 (처음 1400·용량 2000·재생 0) — v3 먹기 거래가 이 장부로 간다
        region.set_editor_property('initial_food_amount', 1400.0)
        region.set_editor_property('food_capacity', 2000.0)
        region.set_editor_property('food_regeneration_rate', 0.0)

        group = unreal.EcoCreatureSpawnGroup()
        group.set_editor_property('region_id', 'Island')
        group.set_editor_property('herbivores', len(deer_pts))
        group.set_editor_property('wolves', 1)
        group.set_editor_property('herbivore_spawn_points', deer_pts)
        group.set_editor_property('wolf_spawn_points', [wolf])
        group.set_editor_property('use_food_patch_position', False)

        spawner = owned('Eco_CreatureRuntime', unreal.EcoCreatureIntegrationSpawner, unreal.Vector(0, 0, 0), 'Coordinator')
        spawner.set_editor_property('herbivore_config', deer_config)
        spawner.set_editor_property('wolf_config', wolf_config)
        spawner.set_editor_property('herbivore_actor_class', deer_bp)
        spawner.set_editor_property('wolf_actor_class', wolf_bp)
        spawner.set_editor_property('footstep_audio_set', footsteps)
        spawner.set_editor_property('groups', [group])
        spawner.set_editor_property('enable_waves', False)
        spawner.set_editor_property('enable_herd_journeys', False)
        spawner.set_editor_property('enable_vegetation', False)
        spawner.set_editor_property('enable_ecosystem_life', False)
        spawner.set_editor_property('global_population_limit', 64)
        spawner.set_editor_property('use_habitat_streaming', True)
        spawner.set_editor_property('habitat_streaming_radius', 10000.0)
        spawner.set_editor_property('day_seconds', 60.0)
        spawner.set_editor_property('night_seconds', 60.0)
        spawner.set_editor_property('use_v3_policy', True)
        spawner.set_editor_property('v3_use_authored_shelters', False)
        try:
            spawner.set_editor_property('v3_island_stage', True)
            rep['island_flag'] = True
        except Exception as e:  # 새 칸이 들어간 빌드 전이면 없다 — 다시 돌리면 켠다
            rep['island_flag'] = False
            rep['island_flag_error'] = str(e)

        start = owned('Eco_PlayerStart_Island', unreal.PlayerStart, view + unreal.Vector(0, 0, 200), 'Observer')
        start.set_actor_rotation(unreal.Rotator(pitch=-20, yaw=45, roll=0), False)

        ws = world.get_world_settings()
        ws.modify()
        ws.set_editor_property('default_game_mode', unreal.EcoCreatureIntegrationGameMode)

    assets.set_metadata_tag(world, 'EcoV3Owner', OWNER)
    assets.set_metadata_tag(world, 'EcoV3CopySource', SOURCE)
    if not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError('맵·외부 액터 저장 실패')
    rep['metadata'] = {k: assets.get_metadata_tag(world, k) for k in ('EcoV3Owner', 'EcoV3CopySource')}
    rep['region'] = {'center': list(REGION_CENTER), 'extent': list(REGION_EXTENT), 'arrival': xyz(view)}
    rep['team_fallback'] = {'deer': [xyz(p) for p in deer_pts], 'wolf': xyz(wolf)}
    rep['actor_descs_after'] = len(lib.get_actor_descs())
    rep['ok'] = True
    unreal.log('ECOV3_ISLAND_COPY_DONE ' + TARGET + ' flag=' + str(rep['island_flag']))
except Exception as e:  # 보고만 하고 끝낸다
    rep['ok'] = False
    rep['error'] = str(e)
    rep['trace'] = traceback.format_exc()
    unreal.log_error('ECOV3_ISLAND_COPY_FAILED ' + str(e))
if OUT:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
unreal.SystemLibrary.quit_editor()

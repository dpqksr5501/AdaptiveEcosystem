"""Author the ecology integration on the owned copy of the SHC island."""
import json
from pathlib import Path

import unreal

SOURCE = '/Game/Map/LV_SHC_IslandEcosystem1_WP'
TARGET = '/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed'
OWNER = 'JYU.IslandEcology'
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assets = unreal.EditorAssetLibrary
if assets.does_asset_exist(TARGET):
    assert levels.load_level(TARGET)
else:
    assert levels.new_level_from_template(TARGET, SOURCE)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().split('.')[0] == TARGET
assert unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world)
existing = actors.get_all_level_actors()
for actor in existing:
    if OWNER in [str(tag) for tag in actor.tags] or actor.get_class().get_name() in (
            'BP_SHC_RainRegionalWeather_C', 'BP_SHC_SnowRegionalWeather_C'):
        actors.destroy_actor(actor)
    elif isinstance(actor, (unreal.EcologyRegion, unreal.EcoCreatureIntegrationSpawner, unreal.EcoRegionEnvironmentAdapter)):
        raise RuntimeError('Unexpected existing ecology writer: ' + actor.get_actor_label())
existing = actors.get_all_level_actors()


def asset(path):
    value = assets.load_asset('/Game/JYU/' + path)
    if not value:
        raise RuntimeError('Missing ' + path)
    return value


def bp(path):
    value = assets.load_blueprint_class('/Game/JYU/' + path)
    if not value:
        raise RuntimeError('Missing class ' + path)
    return value


def spawn(cls, name, point, **properties):
    actor = actors.spawn_actor_from_class(cls, point)
    actor.set_actor_label('JYU_Island_' + name)
    actor.set_editor_property('tags', [OWNER])
    actor.set_editor_property('is_spatially_loaded', False)
    for key, value in properties.items():
        actor.set_editor_property(key, value)
    return actor


def ground(x, y, z=3100):
    result = unreal.EcoCreatureAnimationBuilder.project_placement_point(world, unreal.Vector(x, y, z))
    if isinstance(result, tuple) and result[0]:
        return result[1]
    if isinstance(result, unreal.Vector):
        return result
    raise RuntimeError(f'Ground probe failed at {x}, {y}')


profiles = {name: asset('Ecosystem/Natural/DA_JYU_Habitat_' + name)
            for name in ('Alpine', 'TemperateMosaic')}


def mark_presentation(actor, tag):
    if tag not in [str(value) for value in actor.tags]:
        actor.set_editor_property('tags', list(actor.tags) + [tag])


# The natural presentation profile resolves authored lights by tag.
sun_tag = str(profiles['TemperateMosaic'].get_editor_property('sun_tag'))
moon_tag = str(profiles['TemperateMosaic'].get_editor_property('moon_tag'))
exposure_tag = str(profiles['TemperateMosaic'].get_editor_property('exposure_tag'))
lights = [actor for actor in existing if isinstance(actor, unreal.DirectionalLight)]
team_lights = [actor for actor in lights if OWNER not in [str(value) for value in actor.tags]]
if team_lights:
    sun = next((actor for actor in team_lights if sun_tag in [str(value) for value in actor.tags]), None)
    if sun is None:
        sun = max(team_lights, key=lambda actor: actor.get_component_by_class(unreal.DirectionalLightComponent).intensity)
        mark_presentation(sun, sun_tag)
    component = sun.get_component_by_class(unreal.DirectionalLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_editor_property('forward_shading_priority', 1)
if not any(moon_tag in [str(value) for value in actor.tags] for actor in team_lights):
    moon = spawn(unreal.DirectionalLight, 'Moon', unreal.Vector())
    mark_presentation(moon, moon_tag)
    component = moon.get_component_by_class(unreal.DirectionalLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_intensity(0.)
    component.set_editor_property('cast_shadows', False)
    component.set_editor_property('atmosphere_sun_light', False)
    moon.set_actor_rotation(unreal.Rotator(pitch=-35, yaw=125), False)
for actor in existing:
    if isinstance(actor, unreal.SkyLight):
        mark_presentation(actor, 'Eco.Sky')
    elif isinstance(actor, unreal.PostProcessVolume) and actor.get_editor_property('unbound'):
        mark_presentation(actor, exposure_tag)

# Each stage is a local test area, not a claim about the full island biome boundary.
stages = (
    ('Snowfield', (20000, -10000, 3100), 'Alpine', -4, .52, .18, 0, .68),
    ('Grassland', (90000, 60000, -4000), 'TemperateMosaic', 18, .50, .58, 0, .61),
    ('Riverbank', (36500, 34800, 3100), 'TemperateMosaic', 14, .72, .66, 1, .28),
    ('Highland', (50700, 49500, 3100), 'Alpine', 7, .42, .36, 2, .74),
)
groups = []
report = []
region_profiles = {}
for ordinal, (name, hint, profile, temp, humidity, rain, plant, drainage) in enumerate(stages):
    point = ground(*hint)
    env = unreal.RegionEnvironmentState()
    env.set_editor_property('temperature', temp)
    env.set_editor_property('humidity', humidity)
    env.set_editor_property('rainfall', 0.)
    region = spawn(unreal.EcologyRegion, name, point, region_id=name, environment_state=env,
                   initial_food_amount=1200., food_capacity=1800., food_regeneration_rate=3.,
                   ecological_comfort_population=36)
    region.get_editor_property('region_bounds').set_box_extent(unreal.Vector(4200, 4200, 2500), False)
    spawn(bp('Ecosystem/BP_JYU_EcosystemWeather'), name + '_Rain', point, region_ids=[name],
          rain_phase_offset_seconds=ordinal*22., wet_rainfall=rain)
    habitat = spawn(unreal.EcoVegetationHabitat, name + '_Plants', point,
                    region_id=name, habitat_id=name + '_Main', growth_profile=profiles[profile],
                    plant=plant, drainage=drainage, shade=.22, priority=10)
    habitat.get_editor_property('bounds').set_box_extent(unreal.Vector(2400, 2400, 450), False)
    group = unreal.EcoCreatureSpawnGroup()
    for key, value in dict(region_id=name, herbivores=12, wolves=4,
                           use_food_patch_position=True, food_patch_position=point).items():
        group.set_editor_property(key, value)
    groups.append(group)
    region_profiles[name] = profiles[profile]
    report.append(dict(region=name, center_cm=[point.x, point.y, point.z], profile=profile))

start = ground(89400, 58100, -4000)
spawn(unreal.PlayerStart, 'PlayerStart', start + unreal.Vector(0, 0, 120))
runtime = spawn(unreal.EcoCreatureIntegrationSpawner, 'Runtime', start,
                groups=groups, use_v3_policy=True, v3_deer_per_region=12,
                enable_ecosystem_life=True, enable_vegetation=True, use_habitat_streaming=True,
                habitat_streaming_radius=16000., global_population_limit=96,
                herbivore_config=asset('Config/EC_JYU_V3_Deer'), wolf_config=asset('Config/EC_JYU_V3_Wolf'),
                herbivore_actor_class=bp('Ecosystem/Natural/BP_EcoNaturalDeer'), wolf_actor_class=bp('Creatures/BP_JYU_Wolf'),
                footstep_audio_set=asset('Audio/DA_JYU_Footsteps'), vegetation_field_class=bp('Ecosystem/BP_JYU_VegetationField'),
                natural_habitat_profile=profiles['TemperateMosaic'], region_habitat_profiles=region_profiles)
world.get_world_settings().set_editor_property('default_game_mode', bp('Config/BP_JYU_IntegrationGameMode'))
runtime.validate_editor_setup()
assert levels.save_current_level()

out = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
(out / 'IslandEcologyAuthoring.json').write_text(json.dumps(dict(regions=report), indent=2), encoding='utf8')
unreal.log('JYU_ISLAND_AUTHORING_FINISHED')

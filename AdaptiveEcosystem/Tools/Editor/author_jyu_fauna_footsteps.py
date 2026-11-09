"""Import selected Vault wave data and author the owned fauna map's footstep set."""

import array
import io
import math
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import wave

import unreal


ROOT = "/Game/JYU/Fauna/Audio"
OWNER = "JYU.Fauna.Footsteps"
VAULT = Path(r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\FOOTSTEP26c687a65462V1\data\Content\Footstep_Essentials\Wavs")
ASSETS = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()

# Walk variants, run variants, propagation and mix multipliers.
SURFACES = {
    "Grass": ("GRASS", (4, 7), (1, 4), .82, .92),
    "Dry": ("SOIL", (1, 4), (1, 7), 1., 1.),
    "Snow": ("SNOW", (1, 7), (4, 7), .72, .88),
    "Water": ("WATER", (4, 7), (4, 7), 1.15, 1.),
    "Wet": ("MUD", (1, 7), (4, 7), .78, .86),
    "Stone": ("ROCKS", (1, 4), (4, 7), 1.24, 1.),
    "Wood": ("WOOD", (1, 4), (1, 7), 1.30, .91),
}

# Speed and spacing are in centimeters, playback and gameplay range use independent values.
PROFILES = {
    "Herbivore": (300, 900, 67, 117, .73, 2400, 1.06, 1470, 0, 2250, .38, .14, True),
    "Wolf": (275, 740, 52, 87, .59, 1950, .94, 1250, .83, 2600, .46, .12, False),
    "Pig": (130, 315, 36, 53, .70, 1900, .98, 1350, 0, 1540, .32, .17, True),
    "Fox": (130, 420, 30, 58, .44, 1380, 1.20, 800, .72, 2350, .45, .10, False),
    "Crow": (70, 145, 21, 32, .33, 920, 1.32, 550, 0, 1400, .29, .18, False),
    "Leopard": (150, 530, 46, 82, .53, 1720, .86, 990, .85, 1950, .40, .14, False),
    "Buffalo": (100, 240, 49, 76, .90, 3100, .76, 2400, 0, 1230, .29, .21, True),
    "Rat": (55, 220, 8, 19, .19, 520, 1.52, 310, 0, 1700, .44, .12, False),
    "Player": (360, 900, 88, 148, .78, 3000, 1.0, 2250, 1, 0, .30, .18, False),
}
KEYS = ("walk_speed", "run_speed", "walk_spacing", "run_spacing", "volume", "playback_range",
        "pitch", "noise_range", "threat", "hearing_range", "occluded_hearing", "hearing_threshold", "hoof")


def set_props(obj, **values):
    for name, value in values.items():
        obj.set_editor_property(name, value)
    return obj


def save(obj):
    ASSETS.set_metadata_tag(obj, "JYUOwner", OWNER)
    if not ASSETS.save_loaded_asset(obj, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {obj.get_path_name()}")


def owned(name, original=None, cls=None, factory=None):
    path = f"{ROOT}/{name}"
    if ASSETS.does_asset_exist(path):
        asset = unreal.load_asset(path)
        if ASSETS.get_metadata_tag(asset, "JYUOwner") != OWNER:
            raise RuntimeError(f"Unexpected existing asset {path}")
        return asset
    asset = ASSETS.duplicate_asset(original, path) if original else TOOLS.create_asset(name, ROOT, cls, factory)
    if not asset:
        raise RuntimeError(f"Could not create {path}")
    ASSETS.set_metadata_tag(asset, "JYUOwner", OWNER)
    return asset


def read_pcm(path):
    raw = path.read_bytes()
    start = raw.find(b"RIFF")
    if start < 0 or raw[start + 8:start + 12] != b"WAVE":
        raise RuntimeError(f"Could not locate uncompressed source audio in {path}")
    end = start + 8 + struct.unpack_from("<I", raw, start + 4)[0]
    if end > len(raw):
        raise RuntimeError(f"Incomplete wave data in {path}")
    with wave.open(io.BytesIO(raw[start:end])) as audio:
        if (audio.getnchannels(), audio.getsampwidth()) != (1, 2):
            raise RuntimeError(f"Expected mono PCM16 in {path}")
        samples = array.array("h")
        samples.frombytes(audio.readframes(audio.getnframes()))
        return audio.getframerate(), samples


def voice(samples, rate, mode):
    peak = max(abs(value) for value in samples)
    if mode in ("Paw", "Hoof"):
        # Short material texture, with the shoe's long heel-to-toe tail removed.
        onset = next(i for i, value in enumerate(samples) if abs(value) > .19 * peak)
        clip = samples[max(0, onset - int(.018 * rate)):onset + int((.115 if mode == "Paw" else .205) * rate)]
        cutoff = 185 if mode == "Paw" else 1050
        coefficient = 1. - math.exp(-2. * math.pi * cutoff / rate)
        filtered = []
        low = 0.
        for index, value in enumerate(clip):
            low += coefficient * (value - low)
            envelope = min(1., index / (.003 * rate), (len(clip) - 1 - index) / (.026 * rate))
            filtered.append((value - low if mode == "Paw" else .65 * low + .35 * value) * envelope)
        samples = filtered
    target = {"Paw": .19, "Hoof": .25}.get(mode, .26)
    gain = min(4., target * 32767 / max(1., max(abs(value) for value in samples)))
    return array.array("h", (round(value * gain) for value in samples))


def write_pcm(path, rate, samples):
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(samples.tobytes())


def sound(surface, folder, gait, index, role, staging):
    name = f"SW_{surface}_{role}_{index:02d}"
    destination = f"{ROOT}/Waves/{name}"
    if ASSETS.does_asset_exist(destination):
        return unreal.load_asset(destination)
    source = VAULT / folder / gait / f"WAV_UI_{gait}_{index:02d}.uasset"
    rate, samples = read_pcm(source)
    path = staging / f"{name}.wav"
    write_pcm(path, rate, voice(samples, rate, role))
    task = set_props(unreal.AssetImportTask(), filename=str(path), destination_path=f"{ROOT}/Waves",
                     destination_name=name, automated=True, replace_existing=False, save=False)
    TOOLS.import_asset_tasks([task])
    imported = next((item for item in task.get_objects() if isinstance(item, unreal.SoundWave)), None)
    if not imported:
        raise RuntimeError(f"Could not import {name}")
    save(imported)
    return imported


def configure(world, runtime):
    set_asset = owned("DA_FaunaFootsteps", "/Game/JYU/Audio/DA_JYU_Footsteps")
    attenuation = owned("SA_FaunaFootsteps", "/Game/Audio/Footsteps/Settings/SA_EcoFootsteps")
    concurrency = owned("SC_FaunaFootsteps", "/Game/Audio/Footsteps/Settings/SC_EcoFootsteps")
    profiles = {name: set_props(unreal.EcoFootstepProfile(), **dict(zip(KEYS, values))) for name, values in PROFILES.items()}
    saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
    surface_config = {}
    materials = {}
    with TemporaryDirectory(prefix="FaunaFootstepImport-", dir=saved) as temp:
        for name, (folder, walks, runs, distance, volume) in SURFACES.items():
            pm = unreal.load_asset(f"/Game/JYU/Audio/Surfaces/PM_JYU_{name}") if name not in ("Stone", "Wood") else None
            if not pm:
                pm = owned(f"PM_Fauna_{name}", cls=unreal.PhysicalMaterial, factory=unreal.PhysicalMaterialFactoryNew())
                save(pm)
            materials[name] = pm
            enum = getattr(unreal.EcoFootstepSurface, name.upper())
            clips = {field: [sound(name, folder, gait, i, role, Path(temp)) for i in variants]
                     for field, gait, variants, role in (("player_walk", "WALK", walks, "BootWalk"),
                     ("player_run", "RUN", runs, "BootRun"), ("animal", "WALK", walks, "Paw"),
                     ("hoof", "RUN", runs, "Hoof"))}
            surface_config[enum] = set_props(unreal.EcoFootstepSurfaceAudio(), materials=[pm],
                                             noise_multiplier=distance, volume_multiplier=volume, **clips)
    set_props(set_asset, profiles=profiles, surfaces=surface_config, grass_regions=["FaunaMeadow"])
    if not set_asset.configure_playback(attenuation, concurrency):
        raise RuntimeError("Could not configure fauna playback")
    for asset in (set_asset, attenuation, concurrency):
        save(asset)
    runtime.set_editor_property("footstep_audio_set", set_asset)
    strips(world, materials)
    unreal.log(f"ECO_FAUNA_FOOTSTEPS_READY voices={len(profiles)} surfaces={len(surface_config)}")


def strips(world, materials):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing = {actor.get_actor_label(): actor for actor in actors.get_all_level_actors()}
    colors = ((.16, .34, .09), (.28, .14, .07), (.62, .72, .8), (.055, .26, .38),
              (.18, .10, .065), (.25, .28, .31), (.4, .2, .08))
    edit = unreal.MaterialEditingLibrary
    cube = unreal.load_asset("/Engine/BasicShapes/Cube")
    for index, (name, pm) in enumerate(materials.items()):
        material = owned(f"M_Fauna_{name}", cls=unreal.Material, factory=unreal.MaterialFactoryNew())
        if not edit.get_material_expressions(material):
            color = edit.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -220, 0)
            color.set_editor_property("constant", unreal.LinearColor(*colors[index], 1.))
            edit.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
        material.set_editor_property("phys_material", pm)
        edit.recompile_material(material)
        save(material)
        label = f"Fauna_Footstep_{name}"
        location = unreal.Vector((index - 3) * 420., -4350., .5)
        actor = existing.get(label) or actors.spawn_actor_from_class(unreal.StaticMeshActor, location)
        actor.set_actor_label(label)
        actor.set_actor_scale3d(unreal.Vector(3.8, 12., .025))
        component = actor.static_mesh_component
        component.set_static_mesh(cube)
        component.set_material(0, material)
        component.set_phys_material_override(pm)

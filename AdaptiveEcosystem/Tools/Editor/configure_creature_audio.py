"""Import converted user footsteps, configure SA/concurrency and opt-in animal runtime.

Run convert_footsteps.py first, then run this file in the Unreal Editor Python console
with LV_Ecosystem_IntegrationTest open. Re-running updates our assets/owned coordinator.
Terrain, resource values, PPO weights, network serialization and other Actors are untouched.
"""
import json
import os
import unreal

ROOT = "/Game/Audio/Footsteps"
MAP = "/Game/Map/LV_Ecosystem_IntegrationTest"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def save(asset):
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Save failed: " + asset.get_path_name())


def settings(name, cls, factory):
    path = ROOT + "/Settings/" + name
    asset = unreal.load_asset(path)
    if not asset:
        asset = TOOLS.create_asset(name, ROOT + "/Settings", cls, factory)
    if not asset or not isinstance(asset, cls):
        raise RuntimeError("Missing/wrong-class setting: " + path)
    return asset


def configure():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not world.get_path_name().startswith(MAP + "."):
        raise RuntimeError("Open the team's integration map before configuring its coordinator")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    coordinators = [a for a in actors if isinstance(a, unreal.EcoCreatureIntegrationSpawner)
                    and a.get_actor_label() == "Eco_CreatureRuntime" and "EcoProductionPlacementV1" in [str(t) for t in a.tags]]
    if len(coordinators) != 1:
        raise RuntimeError("Expected one loaded, owned Eco_CreatureRuntime coordinator")
    with open(os.path.join(PROJECT, "Saved/FootstepImportManifest.json"), encoding="utf-8") as stream:
        manifest = json.load(stream)
    tasks = []
    for row in manifest:
        source = os.path.join(PROJECT, row["wav"])
        if not os.path.isfile(source):
            raise RuntimeError("Conversion missing: " + source)
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", source)
        task.set_editor_property("destination_path", ROOT + "/" + row["surface"])
        task.set_editor_property("destination_name", row["asset_name"])
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        tasks.append(task)
    TOOLS.import_asset_tasks(tasks)
    clips = {"Grass": [], "Dry": []}
    for row, task in zip(manifest, tasks):
        sound = unreal.load_asset(ROOT + "/" + row["surface"] + "/" + row["asset_name"])
        if not isinstance(sound, unreal.SoundWave) or sound.get_editor_property("duration") <= 0:
            raise RuntimeError("SoundWave import failed: " + row["asset_name"])
        clips[row["surface"]].append(sound)
    if not clips["Grass"] or not clips["Dry"]:
        raise RuntimeError("Both terrain groups need at least one imported clip")
    sa = settings("SA_EcoFootsteps", unreal.SoundAttenuation, unreal.SoundAttenuationFactory())
    sc = settings("SC_EcoFootsteps", unreal.SoundConcurrency, unreal.SoundConcurrencyFactory())
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", unreal.EcoFootstepAudioSet)
    audio = settings("DA_EcoFootsteps", unreal.EcoFootstepAudioSet, factory)
    audio.modify()
    audio.set_editor_property("grass", clips["Grass"])
    audio.set_editor_property("dry", clips["Dry"])
    if not audio.configure_playback(sa, sc):
        raise RuntimeError("Spatial/concurrency configuration failed")
    for asset in (sa, sc, audio):
        save(asset)
    for kind in ("Deer", "Wolf"):
        bp = unreal.load_asset("/Game/Creatures/Integrated/BP_Eco" + kind)
        if not bp:
            raise RuntimeError("Animal Blueprint missing: " + kind)
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        cdo = unreal.get_default_object(unreal.BlueprintEditorLibrary.generated_class(bp))
        if not cdo.get_editor_property("footsteps"):
            raise RuntimeError("Native Footsteps component missing from " + kind)
        save(bp)
    coordinator = coordinators[0]
    coordinator.modify()
    coordinator.set_editor_property("footstep_audio_set", audio)
    if not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError("Owned coordinator/map save failed")
    result = {"map": MAP, "audio_set": audio.get_path_name(), "grass": len(clips["Grass"]), "dry": len(clips["Dry"]),
              "ai_emission_range_cm": audio.get_editor_property("noise_range"), "audible_inner_cm": 300, "audible_outer_cm": 4000}
    with open(os.path.join(PROJECT, "Saved/FootstepEditorSetup.json"), "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    unreal.log("CREATURE_AUDIO_SETUP_OK " + json.dumps(result))


if __name__ == "__main__":
    configure()

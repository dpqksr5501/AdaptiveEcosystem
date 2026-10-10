"""Apply reviewed foot contacts to owned copies, then update the existing native BS/BP.
Original AnimalVarietyPack assets and unrelated notify tracks are preserved.
"""
import json
from pathlib import Path
import unreal

ROOT = "/Game/Creatures/Integrated"
FOLDER = ROOT + "/FootContacts"
SAVED = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
manifest = json.loads((Path(__file__).resolve().parent / "Data/creature_foot_contacts.json").read_text(encoding="utf-8"))
lib = unreal.AnimationLibrary
unreal.EditorAssetLibrary.make_directory(FOLDER)
report = {}
for kind, clips in manifest.items():
    animations = {}
    for suffix, record in clips.items():
        path = FOLDER + "/ANIM_Eco" + kind + "_" + suffix
        clip = unreal.load_asset(path)
        if not clip:
            clip = unreal.EditorAssetLibrary.duplicate_asset(record["source"].split(".")[0], path)
        if not isinstance(clip, unreal.AnimSequence):
            raise RuntimeError("Owned contact animation missing: " + path)
        tracks = [str(n) for n in lib.get_animation_notify_track_names(clip)]
        if "EcoFootsteps" not in tracks:
            lib.add_animation_notify_track(clip, "EcoFootsteps", unreal.LinearColor(.2,.8,.3,1))
        lib.remove_animation_notify_events_by_name(clip, "EcoFootContact")
        for marker in record["markers"]:
            notify = lib.add_animation_notify_event(clip, "EcoFootsteps", marker["time"], unreal.EcoAnimNotifyFootstep)
            if not notify:
                raise RuntimeError("Notify creation failed " + path)
            notify.set_editor_property("foot_bone", marker["bone"])
        if not unreal.EditorAssetLibrary.save_loaded_asset(clip, only_if_is_dirty=False):
            raise RuntimeError("Save failed " + path)
        animations[suffix] = clip
    prefix, folder = ("ANIM_Wolf", "/Game/AnimalVarietyPack/Wolf/Animations") if kind == "Wolf" else (
        "ANIM_DeerStag", "/Game/AnimalVarietyPack/DeerStagAndDoe/Animations")
    idle = unreal.load_asset(folder + "/" + prefix + "_IdleBreathe")
    blend = unreal.load_asset(ROOT + "/BS_Eco" + kind + "_Turning")
    blueprint = unreal.load_asset(ROOT + "/BP_Eco" + kind)
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_turning(blend, idle, animations["Walk"],
        animations["WalkTurnL"], animations["WalkTurnR"], animations["Run"],
        animations.get("RunTurnL"), animations.get("RunTurnR"), 300., 900.):
        raise RuntimeError("BS validation failed: " + kind)
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_footstep_notifies(blueprint, True):
        raise RuntimeError("BP notify setting did not survive compilation: " + kind)
    for asset in (blend, blueprint):
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
            raise RuntimeError("BS/BP save failed")
    report[kind] = {"clips": {k:v.get_path_name() for k,v in animations.items()}, "notify_count": sum(len(v["markers"]) for v in clips.values())}
(SAVED / "CreatureContactSetup.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
unreal.log("CREATURE_CONTACT_SETUP_OK " + str(report))

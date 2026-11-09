"""Unsaved standalone PIE: existing common player GameMode, real GAS input and camera recovery."""
import unreal as u
import time,json,traceback
from pathlib import Path
root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
out=root/"Saved/RifleValidation";out.mkdir(parents=True,exist_ok=True)
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert levels.load_level("/Game/JWJ/1102_Integration_JWJ")
mode=u.load_asset("/Game/JWJ/Gameplay/BP_EcoGameMode_Common")
assert mode
settings=editor.get_editor_world().get_world_settings()
old_mode=settings.get_editor_property("default_game_mode")
settings.set_editor_property("default_game_mode",mode.generated_class())
aim_action=u.load_asset("/Game/JWJ/Weapons/IA_AimRifle")
fire_action=u.load_asset("/Game/JWJ/Weapons/IA_FireRifle")
state={"deadline":time.monotonic()+110,"phase":0,"shots":[],"outcomes":[]}
def shot(execution,muzzle,end):state["shots"].append({"execution":execution,"distance":(end-muzzle).length()})
def outcome(result):state["outcomes"].append(str(result.get_editor_property("result")))
def finish(ok,error=""):
    state["done"]=True
    (out/"PIE.json").write_text(json.dumps({"result":"PASS" if ok else "FAIL","error":error,"shots":state["shots"],"outcomes":state["outcomes"]},indent=2))
    u.log("[EcoRiflePIE] "+("PASS" if ok else "FAIL "+error))
    levels.editor_request_end_play()
    settings.set_editor_property("default_game_mode",old_mode)
def tick(dt):
    try:
        if state.get("done"):
            if not editor.get_game_world():
                u.unregister_slate_post_tick_callback(handle)
                if "-RifleVerifyQuit" in u.SystemLibrary.get_command_line():u.SystemLibrary.quit_editor()
            return
        assert time.monotonic()<state["deadline"],"timeout"
        world=editor.get_game_world()
        if not world:return
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn:return
        now=u.GameplayStatics.get_time_seconds(world)
        if now<3:return
        avatar=pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
        aim=pawn.get_component_by_class(u.EcoAimComponent)
        fire=pawn.get_component_by_class(u.EcoWeaponFireComponent)
        equip=pawn.get_component_by_class(u.EcoEquipmentComponent)
        if state["phase"]==0:
            assert equip.get_editor_property("weapon"),"weapon did not equip"
            fire.on_shot.add_callable(shot);fire.on_damage_outcome.add_callable(outcome)
            boom=pawn.get_component_by_class(u.SpringArmComponent)
            state["length"]=boom.get_editor_property("target_arm_length")
            pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
            pawn.set_actor_location(u.Vector(0,0,8000),False,False)
            avatar.press_configured_action(fire_action)
            avatar.release_configured_action(fire_action)
            assert not state["shots"],"unaimed shot accepted"
            avatar.press_configured_action(aim_action)
            state["start"]=now;state["phase"]=1
        elif state["phase"]==1 and now-state["start"]>.5:
            assert aim.get_editor_property("aiming"),"aim not activated"
            boom=pawn.get_component_by_class(u.SpringArmComponent)
            assert abs(boom.get_editor_property("target_arm_length")-200)<1,"camera did not blend to aim"
            avatar.press_configured_action(fire_action);avatar.release_configured_action(fire_action)
            assert len(state["shots"])==1,"single click did not shoot exactly once"
            avatar.press_configured_action(fire_action);avatar.release_configured_action(fire_action)
            assert len(state["shots"])==1,"cadence bypass"
            avatar.release_configured_action(aim_action)
            state["phase"]=2;state["start"]=now
        elif state["phase"]==2 and now-state["start"]>.5:
            assert not aim.get_editor_property("aiming"),"release did not stop aiming"
            boom=pawn.get_component_by_class(u.SpringArmComponent)
            assert abs(boom.get_editor_property("target_arm_length")-state["length"])<1,"camera did not restore"
            avatar.press_configured_action(aim_action)
            equip.unequip()
            assert not aim.get_editor_property("aiming"),"unequip left aiming active"
            finish(True)
    except Exception:finish(False,traceback.format_exc())
handle=u.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()

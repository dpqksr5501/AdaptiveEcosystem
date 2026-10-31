"""Reproducible copied-level PIE audit with normal editor shutdown. No saved edits."""
import time
from pathlib import Path
import unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if "LV_JYU_V3Integration" not in editor.get_editor_world().get_name(): raise RuntimeError("Copied level only")
state={"started":False,"audit":None,"end":None,"deadline":time.monotonic()+240}
levels.editor_request_begin_play()
def run(dt):
    if time.monotonic()>state["deadline"]:
        unreal.log_error("JYU_PIE_RUNNER_TIMEOUT");unreal.unregister_slate_post_tick_callback(runner_handle);levels.editor_request_end_play();unreal.SystemLibrary.quit_editor();return
    world=editor.get_game_world()
    if not state["started"] and world and unreal.GameplayStatics.get_time_seconds(world)>1:
        state["started"]=True
        script=Path(unreal.Paths.project_dir())/"Tools/Editor/audit_jyu_ik_visual.py"
        state["end"]=time.monotonic()+42
        state["audit"]={}
        try: exec(compile(script.read_text(encoding="utf-8"),str(script),"exec"),state["audit"])
        except Exception as error:
            unreal.log_error("JYU_IK_RUNNER_FAILED "+str(error));state["end"]=time.monotonic()+2
    if state["end"] and time.monotonic()>state["end"]:
        unreal.unregister_slate_post_tick_callback(runner_handle);levels.editor_request_end_play();unreal.SystemLibrary.quit_editor()
runner_handle=unreal.register_slate_post_tick_callback(run)

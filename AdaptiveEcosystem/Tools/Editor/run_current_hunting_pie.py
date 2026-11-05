import runpy,unreal,traceback
from pathlib import Path
root=Path(__file__).resolve().parent
try:
    runpy.run_path(str(root/"verify_player_hunting.py"))
except Exception:
    unreal.log_error(traceback.format_exc())
    unreal.SystemLibrary.quit_editor()

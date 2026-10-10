"""PIE preview toggles. Run before Play: paused FOV view from above Forest.
Only the flying observer moves. Animal logical positions and saved level stay unchanged.
"""
import time
import unreal

EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
DEADLINE = time.monotonic() + 60
READY_AT = None
commands = ("eco.Footsteps.Debug 0", "eco.Senses.DrawNoise 0", "eco.Senses.DrawFOV 1",
            "eco.Senses.DrawHearing 0", "eco.Senses.DrawLimit 16")
for command in commands:
    unreal.SystemLibrary.execute_console_command(EDITOR.get_editor_world(), command)


def preview(delta):
    global READY_AT
    world = EDITOR.get_game_world()
    if world:
        coordinator = unreal.GameplayStatics.get_actor_of_class(world, unreal.EcoCreatureIntegrationSpawner)
        player = unreal.GameplayStatics.get_player_controller(world, 0)
        if coordinator and coordinator.is_runtime_ready() and player and player.get_controlled_pawn():
            if READY_AT is None:
                player.get_controlled_pawn().set_actor_location(unreal.Vector(34100, 45500, 2800), False, False)
                player.set_control_rotation(unreal.Rotator(pitch=-90, yaw=-90, roll=0))
                READY_AT = time.monotonic()
            elif time.monotonic() - READY_AT >= 2:
                unreal.GameplayStatics.set_game_paused(world, True)
                unreal.unregister_slate_post_tick_callback(HANDLE)
                unreal.log("CREATURE_SENSE_PREVIEW_READY_PAUSED")
    elif time.monotonic() > DEADLINE:
        unreal.unregister_slate_post_tick_callback(HANDLE)


HANDLE = unreal.register_slate_post_tick_callback(preview)

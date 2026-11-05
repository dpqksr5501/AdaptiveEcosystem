"""Standalone PIE verification. Creates unsaved fixtures and ends PIE on completion."""
import unreal as u
import time, traceback
editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert levels.load_level("/Game/JWJ/1102_Integration_JWJ")
attack=u.load_asset("/Game/Variant_Combat/Input/Actions/IA_ComboAttack")
montage=u.load_asset("/Game/JWJ/Gameplay/AM_EcoUnarmedCombo")
data=u.load_asset("/Game/JWJ/Gameplay/DA_EcoUnarmedCombo")
lengths=[u.load_asset("/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_0"+str(i)).get_play_length() for i in (1,2,3)]
u.log("[ComboVerify] lengths="+str(lengths))
state={"phase":0,"start":None,"sent":set(),"seen":set(),"deadline":time.monotonic()+120,"target":None,"contacts":0}
target=u.get_editor_subsystem(u.EditorActorSubsystem).spawn_actor_from_class(u.StaticMeshActor,u.Vector(0,0,0))
target.set_actor_label("ComboTestTarget")
comp=target.static_mesh_component
comp.set_mobility(u.ComponentMobility.MOVABLE)
comp.set_static_mesh(u.load_asset("/Engine/BasicShapes/Sphere"))
comp.set_collision_object_type(u.CollisionChannel.ECC_WORLD_DYNAMIC)
comp.set_collision_enabled(u.CollisionEnabled.QUERY_ONLY)
target.set_actor_scale3d(u.Vector(.18,.18,.18))
levels.editor_request_begin_play()
def finish(ok):
    u.log("[ComboVerify] "+("PASS" if ok else "FAIL"))
    u.unregister_slate_post_tick_callback(handle)
    levels.editor_request_end_play()
    if state.get("target"):
        u.get_editor_subsystem(u.EditorActorSubsystem).destroy_actor(target)
def tick(dt):
    try:
        assert time.monotonic()<state["deadline"], "timeout"
        world=editor.get_game_world()
        if not world or u.GameplayStatics.get_time_seconds(world)<2: return
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn: return
        mesh=pawn.mesh
        anim=mesh.get_anim_instance()
        hit=pawn.get_component_by_class(u.EcoMeleeHitComponent)
        subsystem=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer))
        now=u.GameplayStatics.get_time_seconds(world)
        if state["start"] is None:
            state["start"]=now
            state["seen"].clear(); state["sent"].clear()
            state["contacts"]=hit.get_editor_property("contact_count")
            state["origin"]=mesh.get_socket_location("Attack_Hand_L")-pawn.get_actor_location()
            state["motion"]=0.0
            pawn.set_actor_location(u.Vector(0,-1500,3400),False,False)
            pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
            if state["target"] is None:
                state["target"]=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.StaticMeshActor) if a.get_actor_label()=="ComboTestTarget")
        state["target"].static_mesh_component.set_collision_profile_name("OverlapAllDynamic")
        elapsed=now-state["start"]
        playing=anim.montage_is_playing(montage)
        section=str(anim.montage_get_current_section(montage)) if playing else "None"
        if playing:
            state["seen"].add(section)
            state["motion"]=max(state["motion"],(mesh.get_socket_location("Attack_Hand_L")-pawn.get_actor_location()-state["origin"]).length())
        idx={"LeftPunch":0,"RightPunch":1,"Kick":2}.get(section,0)
        socket=["Attack_Hand_L","Attack_Hand_R","Attack_Foot"][idx]
        state["target"].set_actor_location(mesh.get_socket_location(socket),False,False)
        if playing and "audit" not in state["sent"]:
            state["sent"].add("audit")
            c=state["target"].static_mesh_component
            u.log("[ComboAudit] pos="+str(state["target"].get_actor_location())+" socket="+str(mesh.get_socket_location(socket))+" collision="+str(c.get_collision_enabled())+" type="+str(c.get_collision_object_type())+" actor="+str(state["target"].get_actor_enable_collision()))
        def press(): subsystem.inject_input_vector_for_action(attack,u.Vector(1,0,0),[],[])
        if elapsed<.06: press()
        if playing:
            pos=anim.montage_get_position(montage)-sum(lengths[:idx])
            frac=pos/lengths[idx]
            key=(state["phase"],idx)
            if state["phase"]==1 and idx<2 and .45<frac<.6 and key not in state["sent"]:
                press(); state["sent"].add(key)
            if state["phase"]==2: press()
            if state["phase"]==3 and idx==0 and .12<frac<.18 and key not in state["sent"]:
                press(); state["sent"].add(key)
            if state["phase"]==4 and frac>.35:
                anim.montage_stop(.01,montage)
        if elapsed>sum(lengths)+1:
            expected={0:{"LeftPunch"},1:{"LeftPunch","RightPunch","Kick"},2:{"LeftPunch"},3:{"LeftPunch"},4:{"LeftPunch"}}[state["phase"]]
            assert state["seen"]==expected, str((state["phase"],state["seen"],expected))
            assert hit.get_editor_property("active_step")==-1
            assert state["motion"]>10, "socket animation motion missing "+str(state["motion"])
            delta=hit.get_editor_property("contact_count")-state["contacts"]
            assert delta==len(expected), "contact dedup "+str((state["phase"],delta,expected))
            u.log("[ComboVerify] Case="+str(state["phase"])+" Sections="+str(state["seen"])+" Contacts="+str(delta)+" MotionCm="+str(state["motion"]))
            state["phase"]+=1; state["start"]=None
            if state["phase"]==5: finish(True)
    except Exception:
        u.log_error("[ComboVerify] "+traceback.format_exc()); finish(False)
handle=u.register_slate_post_tick_callback(tick)

"""Dedicated + two real clients. B hides its local representation and cannot damage it."""
import unreal as u
import time,json,re,traceback
from pathlib import Path
cmd=u.SystemLibrary.get_command_line()
server="-RifleNetworkServer" in cmd
name="Server" if server else re.search(r"-RifleNetworkClient=(\w+)",cmd).group(1)
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/"RifleValidation/Network";out.mkdir(parents=True,exist_ok=True)
u.log("[EcoRifleNetwork] Starting "+name)
state={"world":None,"deadline":time.monotonic()+155,"events":[],"next":0,"shots":0,"accepted":0,"samples":[]}
aim_action=u.load_asset("/Game/JWJ/Weapons/IA_AimRifle")
fire_action=u.load_asset("/Game/JWJ/Weapons/IA_FireRifle")
def inspect(w,key):
    raw=u.EcoCreatureInspectionLibrary.capture_agent(w,key)
    if isinstance(raw,tuple):raw=next(v for v in raw if isinstance(v,str))
    return json.loads(raw) if raw else {}
def shot(execution,muzzle,end):state["accepted"]+=1
def event(v):state["events"].append({"result":str(v.result),"damage":v.applied_damage,"id":int(v.target_stable_agent_id)})
def finish(ok,error=""):
    (out/(name+".json")).write_text(json.dumps({"result":"PASS" if ok else "FAIL","error":error,"events":state["events"],"samples":state["samples"],"accepted":state["accepted"]},indent=2))
    u.log("[EcoRifleNetwork] "+name+" "+("PASS" if ok else "FAIL "+error))
    state["done"]=True
    world=state["world"] or next((w for w in u.ObjectIterator(u.World) if u.GameplayStatics.get_game_state(w)),None)
    if world:u.SystemLibrary.execute_console_command(world,"QUIT")
def tick(dt):
    try:
        assert time.monotonic()<state["deadline"],"network timeout"
        w=next((w for w in u.ObjectIterator(u.World) if w.get_name()=="1102_Integration_JWJ" and u.GameplayStatics.get_game_state(w) and (server or u.GameplayStatics.get_player_controller(w,0))),None)
        state["world"]=w
        if not w:return
        runtimes=u.GameplayStatics.get_all_actors_of_class(w,u.EcoCreatureIntegrationSpawner)
        if not runtimes or not runtimes[0].is_runtime_ready():return
        runtime=runtimes[0]
        if server:
            pcs=[p for p in u.GameplayStatics.get_all_actors_of_class(w,u.PlayerController) if p.get_controlled_pawn()]
            if len(pcs)<2 and "start" not in state:return
            if "target" not in state:
                animals=[inspect(w,k) for k in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(w)]
                target=next(a for a in animals if a.get("species")=="Wolf" and a.get("hp",0)>0)
                state["target"]=int(target["stable_id"]);state["hp"]=target["hp"];state["start"]=time.time()
                (out/"Session.json").write_text(json.dumps({"target":state["target"],"start":state["start"]}))
            animal=inspect(w,state["target"]);elapsed=time.time()-state["start"]
            if animal.get("hp",0)>0:
                point=u.Vector(*animal["native_world_position"])
                for i,pc in enumerate(pcs):
                    pawn=pc.get_controlled_pawn();pawn.player_state.set_invulnerable(True)
                    pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
                    pawn.set_actor_location(point+u.Vector(-650,i*120,96),False,True)
                    pawn.character_movement.stop_movement_immediately()
            if 7<elapsed<8:assert animal.get("hp")==state["hp"],"hidden client damaged the target"
            if elapsed>23:
                assert runtime.get_combat_diagnostics().damage_committed>0,"visible client never applied damage"
                state["samples"].append({"hidden_phase_hp":state["hp"],"committed":runtime.get_combat_diagnostics().damage_committed,"deaths":runtime.get_combat_diagnostics().hunting_deaths})
                finish(True)
        else:
            if not (out/"Session.json").exists():return
            session=json.loads((out/"Session.json").read_text());elapsed=time.time()-session["start"]
            pc=u.GameplayStatics.get_player_controller(w,0);pawn=pc.get_controlled_pawn()
            if not pawn:return
            fire=pawn.get_component_by_class(u.EcoWeaponFireComponent)
            if not state.get("bound"):fire.on_damage_outcome.add_callable(event);fire.on_shot.add_callable(shot);state["bound"]=True
            visuals=[v for v in u.GameplayStatics.get_all_actors_of_class(w,u.EcoCreatureRepresentationActor) if v.get_editor_property("bound")]
            if name=="B":
                for v in visuals:v.set_actor_hidden_in_game(True)
            if int(elapsed) not in state.get("logged",set()):
                state.setdefault("logged",set()).add(int(elapsed))
                eq=pawn.get_component_by_class(u.EcoEquipmentComponent)
                ac=pawn.get_component_by_class(u.EcoAimComponent)
                rr=pawn.get_component_by_class(u.EcoCombatRelevanceComponent)
                u.log("[EcoRifleNetwork][State] "+str((name,int(elapsed),ac.get_editor_property("aiming"),str(eq.get_editor_property("weapon")))))
            target=next((v for v in visuals if int(v.visual_state.stable_agent_id)==session["target"]),None)
            avatar=pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
            if target and 2<elapsed<20:
                camera=pawn.get_component_by_class(u.CameraComponent)
                pc.set_control_rotation(u.MathLibrary.find_look_at_rotation(camera.get_world_location(),target.get_actor_location()+u.Vector(0,0,45)))
                subsystem=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer))
                subsystem.inject_input_vector_for_action(aim_action,u.Vector(1,0,0),[],[])
                allowed=(name=="B" and 3<elapsed<7) or (name=="A" and 10<elapsed<19)
                if allowed and elapsed>=state["next"]:
                    state["next"]=elapsed+.6;subsystem.inject_input_vector_for_action(fire_action,u.Vector(1,0,0),[],[]);state["shots"]+=1
            if elapsed>21:
                assert state["shots"]>0,"configured fire input never sent"
                assert not u.EcoCreatureInspectionLibrary.get_authority_agent_ids(w),"client contains logical authority"
                if name=="A":assert any("COMMITTED" in e["result"] for e in state["events"]),"owner outcome not delivered"
                else:assert not any(e["damage"]>0 for e in state["events"]),"hidden representation received damage"
                state["samples"].append({"visuals":len(visuals),"input_shots":state["shots"]});finish(True)
    except Exception:finish(False,traceback.format_exc())
def ticker(dt):
    tick(dt)
    return not state.get("done",False)
handle=u.register_ticker_callback(ticker,0.0)

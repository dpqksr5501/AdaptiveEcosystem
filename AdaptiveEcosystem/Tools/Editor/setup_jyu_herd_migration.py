"""Create an owned copy of the existing JWJ large integration landscape and author herd corridors.
Original team maps/assets are never saved. Requires the project's editor authoring helpers.
"""
import heapq,json,math
from pathlib import Path
import unreal

SOURCE='/Game/JWJ/Integration_JwJ'
TARGET='/Game/JYU/Maps/LV_JYU_HerdMigration'
OWNER='JYU.HerdMigration.v1'
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets=unreal.EditorAssetLibrary
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'HerdMigration_20261022'
out.mkdir(parents=True,exist_ok=True)
if assets.does_asset_exist(TARGET):
    if not levels.load_level(TARGET):raise RuntimeError('Owned map load failed')
else:
    if not levels.new_level_from_template(TARGET,SOURCE):raise RuntimeError('Team map template copy failed')
world=editor.get_editor_world()
if not world.get_path_name().startswith(TARGET):raise RuntimeError('Source authoring refused')
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Partition load failed')
runtime=[a for a in actors.get_all_level_actors() if isinstance(a,unreal.EcoCreatureIntegrationSpawner)]
if len(runtime)!=1:raise RuntimeError('Expected one shared runtime')
runtime=runtime[0]
runtime.set_editor_property('use_v3_policy',True)
runtime.set_editor_property('v3_deer_per_region',48)
runtime.set_editor_property('v3_use_authored_shelters',True)
runtime.set_editor_property('enable_herd_journeys',True)
runtime.set_editor_property('use_habitat_streaming',True)
runtime.set_editor_property('habitat_streaming_radius',12000)
runtime.set_editor_property('herbivore_actor_class',unreal.load_class(None,'/Game/JYU/Creatures/BP_JYU_Deer.BP_JYU_Deer_C'))
runtime.set_editor_property('wolf_actor_class',unreal.load_class(None,'/Game/JYU/Creatures/BP_JYU_Wolf.BP_JYU_Wolf_C'))
runtime.set_editor_property('footstep_audio_set',unreal.load_asset('/Game/JYU/Audio/DA_JYU_Footsteps'))
runtime.set_editor_property('is_spatially_loaded',False)
world.get_world_settings().set_editor_property('default_game_mode',unreal.load_class(None,'/Game/JYU/Config/BP_JYU_IntegrationGameMode.BP_JYU_IntegrationGameMode_C'))

def ground(x,y,z=3000):
    result=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,unreal.Vector(x,y,z))
    if isinstance(result,unreal.Vector):return result
    if isinstance(result,tuple):
        ok=next((v for v in result if isinstance(v,bool)),False)
        point=next((v for v in result if isinstance(v,unreal.Vector)),None)
        return point if ok else None
    return None

centers={'Barren':(34000,18000),'Forest':(34000,32000),'Highland':(34000,-49000)}
for name,(x,y) in list(centers.items()):
    candidates=sorted(((dx,dy) for dx in range(-6000,6001,500) for dy in range(-6000,6001,500)),key=lambda p:p[0]*p[0]+p[1]*p[1])
    for dx,dy in candidates:
        cy=y+dy
        if name=='Barren' and not -18500<=cy<=18500:continue
        if name=='Forest' and not 31500<=cy<=68500:continue
        if name=='Highland' and not -68500<=cy<=-31500:continue
        if ground(x+dx,cy) is not None:centers[name]=(x+dx,cy);break
    else:raise RuntimeError('No valid stage center '+name)
groups=list(runtime.get_editor_property('groups'))
for group in groups:
    name=str(group.get_editor_property('region_id'))
    if name not in centers:raise RuntimeError('Unexpected team region '+name)
    x,y=centers[name];p=ground(x,y)
    if p is None:raise RuntimeError('Invalid authored stage center '+name)
    group.set_editor_property('use_food_patch_position',True)
    group.set_editor_property('food_patch_position',p)
runtime.set_editor_property('groups',groups)

# Existing safety lifecycle, new owned placements inside the selected native stages.
for actor in list(actors.get_all_level_actors()):
    if isinstance(actor,(unreal.EcoShelterAnchor,unreal.EcoHerdMigrationRoute)):
        actors.destroy_actor(actor)
refuge_class=unreal.load_class(None,'/Game/JYU/Environment/BP_JYU_ProtectedRefuge.BP_JYU_ProtectedRefuge_C')
refuges=[]
for region,(x,y) in centers.items():
    for i,(dx,dy) in enumerate(((-3000,-3000),(-3000,3000),(3000,-3000),(3000,3000))):
        point=ground(x+dx,y+dy)
        if point is None:
            point=next((p for ox,oy in ((500,0),(-500,0),(0,500),(0,-500),(1000,0),(-1000,0)) if (p:=ground(x+dx+ox,y+dy+oy)) is not None),None)
        if point is None:raise RuntimeError('Refuge ground unavailable '+region+str(i))
        actor=actors.spawn_actor_from_class(refuge_class,point)
        actor.set_actor_label('JYU_HerdRefuge_'+region+'_'+str(i))
        actor.set_editor_property('is_spatially_loaded',False)
        actor.set_editor_property('tags',[OWNER]);actor.set_editor_property('radius',1200)
        actor.rebuild_habitat();refuges.append({'region':region,'position':[point.x,point.y,point.z]})

# A* uses actual ground/forbidden-area queries. Native sweeps validate the complete route before departure.
step=500
start=(round(centers['Barren'][0]/step),round(centers['Barren'][1]/step))
finish=(round(centers['Forest'][0]/step),round(centers['Forest'][1]/step))
cache={}
def sample(node):
    if node not in cache:cache[node]=ground(node[0]*step,node[1]*step)
    return cache[node]
def h(node):return math.hypot(node[0]-finish[0],node[1]-finish[1])*step
open_set=[(h(start),0,start)];cost={start:0};previous={};found=False
while open_set:
    _,g,node=heapq.heappop(open_set)
    if g!=cost[node]:continue
    if node==finish:found=True;break
    p=sample(node)
    if p is None:continue
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
        nxt=(node[0]+dx,node[1]+dy)
        if not (40<=nxt[0]<=100 and 20<=nxt[1]<=90):continue
        q=sample(nxt)
        if q is None:continue
        distance=math.hypot(dx,dy)*step
        if abs(q.z-p.z)/distance>.45:continue
        # Midpoints avoid thin excluded terrain between grid nodes.
        if ground((p.x+q.x)*.5,(p.y+q.y)*.5,(p.z+q.z)*.5) is None:continue
        new=g+distance+abs(q.z-p.z)*2
        if new<cost.get(nxt,float('inf')):cost[nxt]=new;previous[nxt]=node;heapq.heappush(open_set,(new+h(nxt),new,nxt))
if not found:raise RuntimeError('No traversable corridor; refuse an artificial bridge or teleport')
nodes=[finish]
while nodes[-1]!=start:nodes.append(previous[nodes[-1]])
nodes.reverse();points=[sample(n) for n in nodes]
route=actors.spawn_actor_from_class(unreal.EcoHerdMigrationRoute,points[0])
route.set_actor_label('JYU_HerdRoute_Barren_Forest')
route.set_editor_property('from_region','Barren');route.set_editor_property('to_region','Forest')
route.set_editor_property('points',points);route.set_editor_property('corridor_width',500)
route.set_editor_property('is_spatially_loaded',False);route.set_editor_property('tags',[OWNER])

# Layer actual neck bones from the existing look clip while the legs retain locomotion.
profiles=[]
for kind in ('Deer','Wolf'):
    profile=unreal.load_asset('/Game/JYU/Animation/DA_JYU_'+kind+'_Animation')
    bp=unreal.load_asset('/Game/JYU/Animation/ABP_JYU_'+kind)
    if not profile or not bp:raise RuntimeError('Missing owned animal animation assets')
    if kind=='Deer':
        clip=profile.get_editor_property('poses')[2].get_editor_property('clip')
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(clip,0,unreal.AnimPoseEvaluationOptions())
        names=[str(v) for v in unreal.AnimPoseExtensions.get_bone_names(pose)]
        neck=next((n for n in names if n.lower()=='neck'),next((n for n in names if 'neck' in n.lower()),None))
        if not neck:raise RuntimeError('No neck branch for moving alert pose')
        profile.set_editor_property('alert_head_bone',neck)
    if not unreal.EcoCreatureAnimationBuilder.build_pose_graph(bp,profile):raise RuntimeError('AnimGraph build failed '+kind)
    assets.save_loaded_asset(profile,only_if_is_dirty=False);assets.save_loaded_asset(bp,only_if_is_dirty=False)
    profiles.append({'animal':kind,'head_bone':str(profile.get_editor_property('alert_head_bone'))})

player=next((a for a in actors.get_all_level_actors() if isinstance(a,unreal.PlayerStart)),None)
if player:
    p=ground(32000,20000)
    if p:player.set_actor_location(p+unreal.Vector(0,0,120),False,False)
assets.set_metadata_tag(world,'JYUOwner',OWNER)
if not levels.save_current_level():raise RuntimeError('Owned map save failed')
(out/'Authoring.json').write_text(json.dumps({'source':SOURCE,'target':TARGET,'centers':centers,'route':[[p.x,p.y,p.z] for p in points],
    'sampled_ground_points':len(cache),'refuges':refuges,'profiles':profiles},ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('HERD_AUTHORING_FINISHED '+TARGET)

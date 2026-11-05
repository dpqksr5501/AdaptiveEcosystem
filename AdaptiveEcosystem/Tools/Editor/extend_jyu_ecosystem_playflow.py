"""Survey owned, physically validated Highland/Barren/Forest corridors.

Uses the native ground/clearance constraint via a bounded editor-only bridge.
Only saves LV_JYU_Ecosystem after the complete route passes. No ecology fixtures.
"""
import heapq
import json
import math
from pathlib import Path
import unreal

TARGET='/Game/JYU/Maps/LV_JYU_Ecosystem'
OWNER='JYU.Ecosystem.Playflow.20261029'
LABEL='JYU_Ecosystem_Highland_Barren_GroundRoute'
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'PlayflowFix_20261029'
out.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if not unreal.EditorAssetLibrary.does_asset_exist(TARGET):raise RuntimeError('Existing owned map required')
if not levels.load_level(TARGET):raise RuntimeError('Owned map could not be loaded')
world=editor.get_editor_world()
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world):raise RuntimeError('Ground streaming unavailable')
all_actors=actors.get_all_level_actors()
runtimes=[a for a in all_actors if isinstance(a,unreal.EcoCreatureIntegrationSpawner)]
if len(runtimes)!=1 or not runtimes[0].get_editor_property('enable_ecosystem_life'):raise RuntimeError('Existing life coordinator required')
regions={str(a.get_editor_property('region_id')):a for a in all_actors if isinstance(a,unreal.EcologyRegion)}
if not {'Highland','Barren','Forest'}.issubset(regions):raise RuntimeError('Authored endpoints missing')
for label in (LABEL,'JYU_Ecosystem_Highland_Forest_GroundRoute'):
    existing=next((a for a in all_actors if a.get_actor_label()==label),None)
    if existing and (not isinstance(existing,unreal.EcoHerdMigrationRoute) or OWNER not in map(str,existing.tags)):
        raise RuntimeError('Route label belongs to another author')

cache={};edges={}
def ground(key):
    if key not in cache:
        result=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,unreal.Vector(key[0],key[1],3000))
        value=None
        if isinstance(result,unreal.Vector):value=result
        elif isinstance(result,tuple) and not any(isinstance(v,bool) and not v for v in result):
            value=next((v for v in result if isinstance(v,unreal.Vector)),None)
        cache[key]=value
    return cache[key]

def reachable(a,b):
    pair=tuple(sorted((a,b)))
    if pair not in edges:
        p,q=ground(a),ground(b)
        # Survey both directions using the maximum supported body radius.
        edges[pair]=bool(p is not None and q is not None
            and unreal.EcoCreatureAnimationBuilder.validate_copied_ground_segment(world,p,q)
            and unreal.EcoCreatureAnimationBuilder.validate_copied_ground_segment(world,q,p))
    return edges[pair]

# Endpoints are 5m inside each native stage; the intervening corridor is actual
# landscape, not a logical region that creates extra food or populations.
start=(34000,-43500);goal=(34000,26500)
if ground(start) is None or ground(goal) is None:raise RuntimeError('Endpoint has no usable ground')
frontier=[(0.,start)];cost={start:0.};parent={};visited=set()
while frontier:
    _,current=heapq.heappop(frontier)
    if current in visited:continue
    visited.add(current)
    if current==goal:break
    if len(visited)>4000:raise RuntimeError('Bounded terrain survey exhausted; map not saved')
    for dx,dy in ((1000,0),(-1000,0),(0,1000),(0,-1000)):
        nxt=(current[0]+dx,current[1]+dy)
        if not 14000<=nxt[0]<=54000 or not -43500<=nxt[1]<=26500:continue
        if not reachable(current,nxt):continue
        step=math.dist((ground(current).x,ground(current).y,ground(current).z),(ground(nxt).x,ground(nxt).y,ground(nxt).z))
        candidate=cost[current]+step
        if candidate>=cost.get(nxt,float('inf')):continue
        cost[nxt]=candidate;parent[nxt]=current
        heapq.heappush(frontier,(candidate+math.dist(nxt,goal),nxt))
if goal not in visited:raise RuntimeError('No actual walkable corridor; map not saved')
keys=[goal]
while keys[-1]!=start:keys.append(parent[keys[-1]])
keys.reverse();points=[ground(k) for k in keys]
length=sum(math.hypot(b.x-a.x,b.y-a.y) for a,b in zip(points,points[1:]))
if len(points)>256 or length>100000:raise RuntimeError('Route exceeds native travel budget')

# Use the surveyed point inside Barren as an optional nearer destination. The
# direct Forest route remains available when Barren itself is depleted.
barren_candidates=[i for i,p in enumerate(points) if 28500<=p.x<=39500 and 12500<=p.y<=23500]
if not barren_candidates:raise RuntimeError('Survey does not enter the intermediate Barren stage')
routes=[]
for destination,label,route_points in (('Barren',LABEL,points[:barren_candidates[0]+1]),
    ('Forest','JYU_Ecosystem_Highland_Forest_GroundRoute',points)):
    existing=next((a for a in all_actors if a.get_actor_label()==label),None)
    route=existing or actors.spawn_actor_from_class(unreal.EcoHerdMigrationRoute,route_points[0])
    if not route:raise RuntimeError('Owned route could not be created')
    route.set_actor_label(label);route.set_editor_property('tags',[OWNER]);route.set_editor_property('is_spatially_loaded',False)
    for key,value in {'from_region':'Highland','to_region':destination,'points':route_points,'bidirectional':True,'enabled':True,
        'corridor_width':600.,'shares_habitat_reports':True}.items():route.set_editor_property(key,value)
    if not route.is_valid_route():raise RuntimeError('Native route authoring validation failed')
    for a,b in (('Highland',destination),(destination,'Highland')):
        ids=list(regions[a].get_editor_property('adjacent_region_ids'))
        if b not in map(str,ids):regions[a].set_editor_property('adjacent_region_ids',ids+[unreal.Name(b)])
    routes.append({'destination':destination,'label':label,'points':len(route_points)})
if not levels.save_current_level():raise RuntimeError('Owned map save failed')
report={'map':TARGET,'owner':OWNER,'routes':routes,'points':[[p.x,p.y,p.z] for p in points],'length_cm':length,
    'ground_probes':len(cache),'validated_edges':sum(edges.values()),'body_radius_cm':40,'bidirectional':True,
    'native_physical_constraint':True,'new_food_region':False,'fixture':False}
(out/'RouteAuthoring.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('PLAYFLOW_ROUTE_AUTHORING_FINISHED '+json.dumps({'points':len(points),'length_cm':length}))

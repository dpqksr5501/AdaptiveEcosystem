import json
from pathlib import Path
import unreal
rows=[]
for kind in ("Deer","Wolf"):
 p=unreal.load_asset("/Game/JYU/Animation/DA_JYU_"+kind+"_Animation")
 c=unreal.load_class(None,"/Game/JYU/Creatures/BP_JYU_"+kind+".BP_JYU_"+kind+"_C")
 mesh=unreal.SkeletalMeshComponent();mesh.set_skeletal_mesh_asset(unreal.get_default_object(c).get_editor_property("visual_mesh"))
 for foot in p.get_editor_property("foot_bones"):
  chain=[str(foot)];bone=foot
  for i in range(5):
   bone=mesh.get_parent_bone(bone);chain.append(str(bone))
  rows.append({"species":kind,"chain":chain})
print(json.dumps(rows,indent=2))
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/"IntegrationV3/FootChains.json";out.write_text(json.dumps(rows,indent=2),encoding="utf-8")

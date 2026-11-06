#include "Player/EcoWeaponAuthoringLibrary.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/SkeletalMeshSocket.h"
bool UEcoWeaponAuthoringLibrary::EnsureGunSocket(USkeletalMesh* Mesh,FName Bone)
{
#if WITH_EDITOR
    if (!Mesh || Mesh->GetRefSkeleton().FindBoneIndex(Bone)==INDEX_NONE) return false;
    if (Mesh->FindSocket(TEXT("socket_Gun"))) return true;
    Mesh->Modify(); auto* Socket=NewObject<USkeletalMeshSocket>(Mesh);
    Socket->SocketName=TEXT("socket_Gun"); Socket->BoneName=Bone;
    Mesh->GetMeshOnlySocketList().Add(Socket); Mesh->MarkPackageDirty(); return true;
#else
    return false;
#endif
}

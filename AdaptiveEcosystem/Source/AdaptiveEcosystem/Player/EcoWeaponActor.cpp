#include "Player/EcoWeaponActor.h"
#include "Player/EcoWeaponDefinition.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Net/UnrealNetwork.h"
AEcoWeaponActor::AEcoWeaponActor()
{
    bReplicates = true; bNetUseOwnerRelevancy = true;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    StaticMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("WeaponMesh")); StaticMesh->SetupAttachment(RootComponent);
    SkeletalMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("AnimatedWeaponMesh")); SkeletalMesh->SetupAttachment(RootComponent);
    StaticMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision); SkeletalMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SkeletalMesh->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    MuzzlePoint = CreateDefaultSubobject<USceneComponent>(TEXT("MuzzlePoint")); MuzzlePoint->SetupAttachment(RootComponent);
}
void AEcoWeaponActor::Initialize(UEcoWeaponDefinition* Data) { Definition=Data; OnRep_Definition(); }
void AEcoWeaponActor::OnRep_Definition()
{
    StaticMesh->SetStaticMesh(Definition ? Definition->StaticMesh : nullptr);
    SkeletalMesh->SetSkeletalMeshAsset(Definition ? Definition->SkeletalMesh : nullptr);
    StaticMesh->SetVisibility(Definition && !Definition->SkeletalMesh);
    SkeletalMesh->SetVisibility(Definition && Definition->SkeletalMesh);
}
bool AEcoWeaponActor::GetMuzzleTransform(FTransform& Out) const
{
    if (!Definition) return false;
    if (bUseMuzzlePoint) { Out=MuzzlePoint->GetComponentTransform(); return !Out.ContainsNaN(); }
    const UMeshComponent* Mesh=Definition->SkeletalMesh ? static_cast<UMeshComponent*>(SkeletalMesh) : StaticMesh.Get();
    if (!Mesh->DoesSocketExist(Definition->MuzzleSocket)) return false;
    Out=Mesh->GetSocketTransform(Definition->MuzzleSocket); return !Out.ContainsNaN();
}
void AEcoWeaponActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{ Super::GetLifetimeReplicatedProps(OutLifetimeProps); DOREPLIFETIME(AEcoWeaponActor,Definition); }

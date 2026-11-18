#include "Creature/Representation/EcoForagePatchVisual.h"

#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Net/UnrealNetwork.h"

AEcoForagePatchVisual::AEcoForagePatchVisual()
{
    PrimaryActorTick.bCanEverTick = false;
    bReplicates = true;
    SetNetUpdateFrequency(4.f);
    Plants = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("Plants"));
    SetRootComponent(Plants);
    WoodyStems = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("WoodyStems"));
    WoodyStems->SetupAttachment(Plants);
    for (auto* Component : {Plants.Get(), WoodyStems.Get()})
    {
        Component->SetMobility(EComponentMobility::Movable);
        Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Component->SetCanEverAffectNavigation(false);
    }
}

void AEcoForagePatchVisual::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AEcoForagePatchVisual, ForageAmount);
}

void AEcoForagePatchVisual::BeginPlay()
{
    Super::BeginPlay();
    if (GetNetMode() != NM_DedicatedServer) RebuildForagePreview();
}

void AEcoForagePatchVisual::RebuildForagePreview()
{
    Plants->ClearInstances();
    WoodyStems->ClearInstances();
    Plants->AddInstances(FullPlantTransforms, false, false, false);
    if (bKeepWoodyStems) WoodyStems->AddInstances(FullPlantTransforms, false, false, false);
    ApplyForageAppearance();
}

void AEcoForagePatchVisual::PublishStockFraction(float Fraction)
{
    if (!HasAuthority() || !FMath::IsFinite(Fraction)) return;
    const uint8 Next = uint8(FMath::RoundToInt(FMath::Clamp(Fraction, 0.f, 1.f) * 255.f));
    if (Next == ForageAmount) return;
    ForageAmount = Next;
    if (GetNetMode() != NM_DedicatedServer) ApplyForageAppearance();
    ForceNetUpdate();
}

void AEcoForagePatchVisual::OnRep_ForageAmount()
{
    ApplyForageAppearance();
}

void AEcoForagePatchVisual::ApplyForageAppearance()
{
    const UStaticMesh* Mesh = Plants->GetStaticMesh();
    if (!Mesh || Plants->GetInstanceCount() != FullPlantTransforms.Num()) return;
    const float Fraction = GetForageFraction();
    const double Bottom = Mesh->GetBoundingBox().Min.Z;
    for (int32 Index = 0; Index < FullPlantTransforms.Num(); ++Index)
    {
        FTransform Instance = FullPlantTransforms[Index];
        const FVector FullScale = Instance.GetScale3D();
        FVector Scale = FullScale;
        if (bKeepWoodyStems)
        {
            // Browsed foliage thins by clump while the independent wood stays at its original size.
            const float Canopy = FMath::Clamp(Fraction * FullPlantTransforms.Num() - Index, 0.f, 1.f);
            Scale *= FMath::Lerp(.001f, 1.f, Canopy);
        }
        else
        {
            Scale.Z *= FMath::Lerp(ResidualHeightFraction, 1.f, Fraction);
        }
        Instance.SetScale3D(Scale);
        Instance.AddToTranslation(FVector(0., 0., Bottom * (FullScale.Z - Scale.Z)));
        Plants->UpdateInstanceTransform(Index, Instance, false, Index + 1 == FullPlantTransforms.Num(), true);
    }
    if (HasActorBegunPlay()) OnForageAppearanceChanged(Fraction);
}
